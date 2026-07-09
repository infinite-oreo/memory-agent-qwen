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

    # ---- 检索 ----
    retrieve_top_k: int = field(default_factory=lambda: int(_env("RETRIEVE_TOP_K", "5")))

    # ---- CORS ----
    cors_origins: list = field(
        default_factory=lambda: _env(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
    )


# 全局单例 —— 进程内唯一配置实体
settings = Settings()
