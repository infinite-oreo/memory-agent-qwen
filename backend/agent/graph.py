# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 langgraph.graph.StateGraph，依赖 agent.nodes 的三节点与 AgentState
[OUTPUT]: 对外提供 run_agent(user_id, message, session_id) -> {reply, memories_used, facts_learned}
[POS]: agent 模块的编排中枢，将认知节点连成 retrieve→reason→store 的单向流
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from langgraph.graph import StateGraph, START, END

from agent.nodes import AgentState, retrieve_memory, reason, store_memory
from memory.short_term import short_term_store


# ============================================================
# 状态图编排 —— 认知的有向流
#   START → retrieve_memory → reason → store_memory → END
# ============================================================
def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("retrieve_memory", retrieve_memory)
    g.add_node("reason", reason)
    g.add_node("store_memory", store_memory)

    g.add_edge(START, "retrieve_memory")
    g.add_edge("retrieve_memory", "reason")
    g.add_edge("reason", "store_memory")
    g.add_edge("store_memory", END)
    return g.compile()


# 编译期单例 —— 图结构不可变, 全进程复用
_app = _build_graph()


async def run_agent(user_id: str, message: str, session_id: str) -> dict:
    """
    驱动一轮完整认知。
    返回 {reply: str, memories_used: list[str], facts_learned: dict}。
    短期记忆在此处闭环更新（user 入、assistant 出）。
    """
    short_term_store.append(session_id, "user", message)

    final: AgentState = await _app.ainvoke(
        {"user_id": user_id, "message": message, "session_id": session_id}
    )

    reply = final.get("reply", "")
    short_term_store.append(session_id, "assistant", reply)

    memories_used = [m["text"] for m in (final.get("retrieved") or [])]
    facts_learned = final.get("stored") or {"profile": {}, "preferences": [], "memories": []}
    return {
        "reply": reply,
        "memories_used": memories_used,
        "facts_learned": facts_learned,
    }
