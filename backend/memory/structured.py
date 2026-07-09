# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 aiosqlite 异步驱动，依赖 config.settings.sqlite_path
[OUTPUT]: 对外提供 init_db / create_user / update_profile / get_user_profile / update_preference
[POS]: memory 模块的结构化用户画像，与 long_term 向量记忆互补的事实真相源
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from datetime import datetime, timezone

import aiosqlite

from config import settings

# ============================================================
# SQLite 表结构 —— 用户画像的关系骨架
#   users:       身份与稳定属性（姓名/研究领域/语言偏好）
#   preferences: 可演化的键值偏好（一对多）
# ============================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id             TEXT PRIMARY KEY,
    name                TEXT,
    research_domain     TEXT,
    language_preference TEXT DEFAULT 'zh',
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
    """建表 —— 幂等，应用启动时调用一次。"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def create_user(
    user_id: str,
    name: str = "",
    research_domain: str = "",
    language_preference: str = "zh",
) -> dict:
    """创建或更新用户基本画像（幂等 upsert）。"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, name, research_domain, language_preference, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                research_domain = excluded.research_domain,
                language_preference = excluded.language_preference
            """,
            (user_id, name, research_domain, language_preference, _now()),
        )
        await db.commit()
    return await get_user_profile(user_id)


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
