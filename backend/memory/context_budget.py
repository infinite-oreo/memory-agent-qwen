# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 tiktoken 做 token 计数（用 cl100k_base 近似估算，无官方 Qwen tokenizer 时的合理替代）
[OUTPUT]: 对外提供 count_tokens / fit_memories / fit_history
[POS]: memory 模块的上下文预算器，在有限 token 窗口内为 reason 节点精选记忆与历史
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text or ""))


def fit_memories(memories: list[dict], budget: int) -> list[dict]:
    """
    按已排序(遗忘重排后, 高分在前)的优先级顺序贪心装入 token 预算。
    一旦装不下就停止——宁可少几条不相关的旧记忆，也不超预算挤占对话本身的空间。
    """
    kept: list[dict] = []
    used = 0
    for m in memories:
        t = count_tokens(m["text"])
        if used + t > budget:
            break
        kept.append(m)
        used += t
    return kept


def fit_history(turns: list[dict], budget: int) -> list[dict]:
    """从最近的对话轮次倒序装入预算，超出则丢弃更早的轮次，保留新近上下文。"""
    kept: list[dict] = []
    used = 0
    for turn in reversed(turns):
        t = count_tokens(turn.get("content", ""))
        if used + t > budget:
            break
        kept.append(turn)
        used += t
    kept.reverse()
    return kept
