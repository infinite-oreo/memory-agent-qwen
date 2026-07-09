# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖标准库 collections，纯内存结构无外部依赖
[OUTPUT]: 对外提供 short_term_store 单例（ShortTermMemory 实例）
[POS]: memory 模块的会话内短期记忆，进程生命周期内的对话滑窗
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from collections import defaultdict, deque


# ============================================================
# 短期记忆 —— 进程内、按 session_id 隔离的对话滑动窗口
#   重启即遗忘，这正是"短期"的本意；持久化交给长期记忆
# ============================================================
class ShortTermMemory:
    def __init__(self, max_turns: int = 20) -> None:
        # 每条 = {"role": "user"|"assistant", "content": str}
        self._sessions: dict[str, deque] = defaultdict(lambda: deque(maxlen=max_turns))

    def append(self, session_id: str, role: str, content: str) -> None:
        self._sessions[session_id].append({"role": role, "content": content})

    def history(self, session_id: str) -> list[dict]:
        return list(self._sessions[session_id])

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# 全局单例 —— 与 FastAPI 进程同生共死
short_term_store = ShortTermMemory()
