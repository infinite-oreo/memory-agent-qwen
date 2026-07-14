# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 python-dotenv 的 load_dotenv，依赖 os.environ 读取运行时环境
[OUTPUT]: 对外提供 settings 单例（Settings 实例），承载全局配置
[POS]: backend 的配置真相源，被 agent/memory/api 各层共同消费
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# ============================================================
# 加载 .env —— 配置的单一真相源，所有秘密从此流入
# ============================================================
load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass
class Settings:
    # ---- Qwen Cloud (OpenAI 兼容接口) ----
    qwen_api_key: str = field(default_factory=lambda: _env("QWEN_API_KEY"))
    qwen_base_url: str = field(
        default_factory=lambda: _env(
            "QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        )
    )
    qwen_model: str = field(default_factory=lambda: _env("QWEN_MODEL", "qwen-max"))

    # ---- 记忆存储路径 ----
    chroma_dir: str = field(default_factory=lambda: _env("CHROMA_DIR", "./chroma_db"))
    sqlite_path: str = field(default_factory=lambda: _env("SQLITE_PATH", "./profiles.db"))

    # ---- Embedding 模型 (多语言, 支持中文) ----
    embed_model: str = field(
        default_factory=lambda: _env(
            "EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        )
    )

    # ---- 遗忘机制 ----
    forgetting_lambda: float = field(
        default_factory=lambda: float(_env("FORGETTING_LAMBDA", "0.01"))
    )
    # 衰减到此分数以下的记忆视为"已遗忘"，定期真删除，而非仅在检索时降权
    forgetting_prune_threshold: float = field(
        default_factory=lambda: float(_env("FORGETTING_PRUNE_THRESHOLD", "0.05"))
    )

    # ---- 去重 ----
    # 新记忆与已有记忆的余弦相似度超过此值，视为同一事实的再次印证，强化旧记忆而非重复入库
    dedup_similarity_threshold: float = field(
        default_factory=lambda: float(_env("DEDUP_SIMILARITY_THRESHOLD", "0.92"))
    )

    # ---- 检索 ----
    # 向量库候选池大小：先按语义+遗忘重排召回这么多条，再由 token 预算动态决定实际注入多少条
    memory_candidate_pool: int = field(
        default_factory=lambda: int(_env("MEMORY_CANDIDATE_POOL", "20"))
    )
    # 注入 system prompt 的长期记忆文本 token 预算（有限上下文窗口内的精选，而非拍脑袋定条数）
    memory_token_budget: int = field(
        default_factory=lambda: int(_env("MEMORY_TOKEN_BUDGET", "800"))
    )
    # 注入 system prompt 的短期对话历史 token 预算
    history_token_budget: int = field(
        default_factory=lambda: int(_env("HISTORY_TOKEN_BUDGET", "1500"))
    )

    # ---- CORS ----
    cors_origins: list = field(
        default_factory=lambda: _env(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
    )


# 全局单例 —— 进程内唯一配置实体
settings = Settings()
