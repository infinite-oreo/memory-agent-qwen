# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 aiosqlite 异步驱动，依赖 config.settings.sqlite_path，依赖标准库 secrets/hmac
[OUTPUT]: 对外提供 init_db / create_user(含签发 api_key) / update_profile / get_user_profile / update_preference / verify_api_key
[POS]: memory 模块的结构化用户画像，与 long_term 向量记忆互补的事实真相源；亦是多用户鉴权的凭证真相源
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import hmac
import secrets
from datetime import datetime, timezone

import aiosqlite

from config import settings

# ============================================================
# SQLite 表结构 —— 用户画像的关系骨架
#   users:       身份与稳定属性（姓名/研究领域/语言偏好/鉴权凭证）
#   preferences: 可演化的键值偏好（一对多）
# ============================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id             TEXT PRIMARY KEY,
    name                TEXT,
    research_domain     TEXT,
    language_preference TEXT DEFAULT 'zh',
    api_key             TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    user_id    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, key),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    """建表 —— 幂等，应用启动时调用一次；随后对老库做 api_key 列的迁移与回填。"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.executescript(_SCHEMA)
        await _migrate_add_api_key_column(db)
        await db.commit()


async def _migrate_add_api_key_column(db: aiosqlite.Connection) -> None:
    """
    幂等迁移：CREATE TABLE IF NOT EXISTS 对已存在的老库不会补列，必须显式 ALTER TABLE。
    老库补列后，为历史遗留的空 api_key 行各签发一把新 key，保证升级前的用户无需人工介入即可继续使用。
    唯一索引也放在这里建（而非 _SCHEMA 里）：ALTER TABLE ADD COLUMN 不支持直接加 UNIQUE 约束，
    且索引必须在列确定存在之后才能建，对新库/老库两条路径统一生效。
    """
    async with db.execute("PRAGMA table_info(users)") as cur:
        cols = [row[1] async for row in cur]
    if "api_key" not in cols:
        await db.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
    await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key)")

    async with db.execute("SELECT user_id FROM users WHERE api_key IS NULL") as cur:
        rows = await cur.fetchall()
    for (user_id,) in rows:
        await db.execute(
            "UPDATE users SET api_key = ? WHERE user_id = ?",
            (secrets.token_urlsafe(32), user_id),
        )


async def create_user(
    user_id: str,
    name: str = "",
    research_domain: str = "",
    language_preference: str = "zh",
) -> dict:
    """
    创建或更新用户基本画像（幂等 upsert）。
    首次创建时签发 api_key；老用户 upsert 时刻意不覆盖 api_key，保证已签发的凭证不轮换。
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, name, research_domain, language_preference, api_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                research_domain = excluded.research_domain,
                language_preference = excluded.language_preference
            """,
            (user_id, name, research_domain, language_preference, secrets.token_urlsafe(32), _now()),
        )
        await db.commit()
    return await get_user_profile(user_id)


async def verify_api_key(user_id: str, api_key: str) -> bool:
    """比对 user_id 与其绑定的 api_key 是否匹配；用户不存在或 key 不匹配都返回 False。"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT api_key FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None or row[0] is None:
        return False
    return hmac.compare_digest(row[0], api_key)


# 可被 LLM 抽取回写的画像字段白名单 —— 防注入, 只此三列可动态更新
_PROFILE_FIELDS = ("name", "research_domain", "language_preference")


async def update_profile(user_id: str, **fields) -> dict:
    """
    部分更新画像：只写入白名单内、值非空的字段，不误伤其余字段。
    用户不存在时自动建壳（upsert），适配 LLM 自动回写场景。
    """
    fields = {k: v for k, v in fields.items() if k in _PROFILE_FIELDS and v}
    if not fields:
        return await get_user_profile(user_id)

    async with aiosqlite.connect(settings.sqlite_path) as db:
        # 确保行存在, 再做选择性更新 —— 让"新用户"与"老用户"走同一条路径
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)",
            (user_id, _now()),
        )
        sets = ", ".join(f"{k} = ?" for k in fields)
        await db.execute(
            f"UPDATE users SET {sets} WHERE user_id = ?",
            (*fields.values(), user_id),
        )
        await db.commit()
    return await get_user_profile(user_id)


async def get_user_profile(user_id: str) -> dict | None:
    """聚合返回用户画像：基本字段 + 全部偏好键值。不存在返回 None。"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        profile = dict(row)

        async with db.execute(
            "SELECT key, value, updated_at FROM preferences WHERE user_id = ?",
            (user_id,),
        ) as cur:
            prefs = await cur.fetchall()
        profile["preferences"] = {
            p["key"]: {"value": p["value"], "updated_at": p["updated_at"]} for p in prefs
        }
        return profile


async def update_preference(user_id: str, key: str, value: str) -> dict:
    """写入/更新单条偏好（upsert）。返回最新用户画像。"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            """
            INSERT INTO preferences (user_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (user_id, key, value, _now()),
        )
        await db.commit()
    return await get_user_profile(user_id)
