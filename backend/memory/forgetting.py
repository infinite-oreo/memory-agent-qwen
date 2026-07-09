# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖标准库 math/datetime，纯函数无外部副作用
[OUTPUT]: 对外提供 decay_score / rerank_by_forgetting
[POS]: memory 模块的认知衰减核心，被 long_term 检索后置调用
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import math
from datetime import datetime, timezone

from config import settings


# ============================================================
# 时间衰减遗忘评分
#   score = semantic_similarity * exp(-lambda * days_since_access)
#   记忆如生命，越久不被唤起，越淡入遗忘的河流
# ============================================================
def _days_since(iso_ts: str) -> float:
    """从 ISO 时间戳到当下的天数；缺失时间戳视为刚发生 (0 天)。"""
    if not iso_ts:
        return 0.0
    try:
        then = datetime.fromisoformat(iso_ts)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.0
    delta = datetime.now(timezone.utc) - then
    return max(delta.total_seconds() / 86400.0, 0.0)


def decay_score(similarity: float, last_access: str, lambda_: float | None = None) -> float:
    """对单条记忆计算衰减后的最终分数。"""
    lam = settings.forgetting_lambda if lambda_ is None else lambda_
    return similarity * math.exp(-lam * _days_since(last_access))


def rerank_by_forgetting(memories: list[dict], lambda_: float | None = None) -> list[dict]:
    """
    对检索结果按"语义相似度 × 时间衰减"重排序。
    输入每条 memory 需含: similarity(float), metadata.last_access(iso str)。
    输出附加 decayed_score 字段并降序排列。
    """
    for m in memories:
        last_access = (m.get("metadata") or {}).get("last_access", "")
        m["decayed_score"] = decay_score(m.get("similarity", 0.0), last_access, lambda_)
    return sorted(memories, key=lambda x: x["decayed_score"], reverse=True)
