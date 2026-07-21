# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖标准库 math/datetime，依赖 config.settings
[OUTPUT]: 对外提供 decay_score / retention_score / rerank_by_forgetting（均支持按 memory_type 分速率衰减）
[POS]: memory 模块的认知衰减核心，被 long_term 检索与剪枝调用
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import math
from datetime import datetime, timezone

from config import settings

# 重要性对衰减速度的影响力：重要性越高，衰减越慢
_IMPORTANCE_ALPHA = 1.0

# 分类衰减速度倍数：情景记忆最快遗忘，语义记忆最慢，程序性记忆居中
# （认知科学共识：情景记忆是"此时此地"绑定事件，脱离语境后价值衰减快；
#  稳定事实/知识应最抗遗忘；习惯偏好会被日常对话反复印证, 取原有默认速度）
# 缺失/未知类型（含分类上线前写入的旧记忆）一律按 1.0 处理，即完全不变的原有行为，
# 保证升级当天不会因历史数据被判定"过期"而触发批量真删除
_MEMORY_TYPE_LAMBDA_MULTIPLIER = {"episodic": 2.0, "semantic": 0.4, "procedural": 1.0}


# ============================================================
# 时间衰减遗忘评分
#   score = semantic_similarity * importance^alpha * exp(-lambda * days_since_access)
#   记忆如生命，越久不被唤起、越不重要，越淡入遗忘的河流；核心事实衰减得更慢
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


def decay_score(
    similarity: float,
    last_access: str,
    importance: float = 0.5,
    lambda_: float | None = None,
    memory_type: str | None = None,
) -> float:
    """对单条记忆计算衰减后的最终分数。lambda_ 显式传参优先；否则按 memory_type 选衰减速度倍数。"""
    if lambda_ is not None:
        lam = lambda_
    else:
        lam = settings.forgetting_lambda * _MEMORY_TYPE_LAMBDA_MULTIPLIER.get(memory_type, 1.0)
    imp = max(float(importance), 1e-6) ** _IMPORTANCE_ALPHA
    return similarity * imp * math.exp(-lam * _days_since(last_access))


def retention_score(
    last_access: str,
    importance: float = 0.5,
    lambda_: float | None = None,
    memory_type: str | None = None,
) -> float:
    """无查询上下文的"当前记忆强度"：供定期真遗忘剪枝判断使用（等价于 similarity=1.0）。"""
    return decay_score(1.0, last_access, importance, lambda_, memory_type)


def rerank_by_forgetting(memories: list[dict], lambda_: float | None = None) -> list[dict]:
    """
    对检索结果按"语义相似度 × 重要性 × 时间衰减(按记忆类型分速率)"重排序。
    输入每条 memory 需含: similarity(float), metadata.last_access(iso str)/importance(float)/memory_type(str)。
    输出附加 decayed_score 字段并降序排列。
    """
    for m in memories:
        meta = m.get("metadata") or {}
        importance = float(meta.get("importance", 0.5))
        m["decayed_score"] = decay_score(
            m.get("similarity", 0.0),
            meta.get("last_access", ""),
            importance,
            lambda_,
            meta.get("memory_type"),
        )
    return sorted(memories, key=lambda x: x["decayed_score"], reverse=True)
