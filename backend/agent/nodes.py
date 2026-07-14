# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 langchain_openai.ChatOpenAI，依赖 memory.long_term/structured/short_term/extractor/context_budget，依赖 config.settings
[OUTPUT]: 对外提供 AgentState 类型 与 retrieve_memory / reason / store_memory 三个异步节点
[POS]: agent 模块的认知原子，被 graph.py 编排为有向状态流
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI

from config import settings
from memory import long_term, structured
from memory.context_budget import fit_history, fit_memories
from memory.extractor import extract_facts
from memory.short_term import short_term_store


# ============================================================
# 状态契约 —— 在节点间单向流动的数据河流
# ============================================================
class AgentState(TypedDict, total=False):
    user_id: str
    session_id: str
    message: str
    profile: dict | None
    retrieved: list[dict]   # 命中的长期记忆 (含 decayed_score)
    reply: str
    stored: dict            # 本轮抽取并回写的结构化事实


# LLM 单例 —— Qwen 通过 OpenAI 兼容接口接入
_llm = ChatOpenAI(
    model=settings.qwen_model,
    api_key=settings.qwen_api_key,
    base_url=settings.qwen_base_url,
    temperature=0.7,
)

# 不值得长期存储的寒暄噪音
_TRIVIAL = {"你好", "hi", "hello", "在吗", "嗨", "谢谢", "thanks", "ok", "好的", "再见"}


# ------------------------------------------------------------
# Node 1: retrieve_memory —— 从向量库与画像库召回相关记忆
#   先按语义+遗忘重排取一个候选池，再用 token 预算精选出真正塞进 prompt 的那几条
# ------------------------------------------------------------
async def retrieve_memory(state: AgentState) -> AgentState:
    user_id, query = state["user_id"], state["message"]
    profile = await structured.get_user_profile(user_id)
    candidates = long_term.retrieve_memory(user_id, query, top_k=settings.memory_candidate_pool)
    retrieved = fit_memories(candidates, settings.memory_token_budget)
    return {"profile": profile, "retrieved": retrieved}


# ------------------------------------------------------------
# Node 2: reason —— 拼装上下文, 调用 Qwen 生成回复
#   短期历史同样受 token 预算约束，而非无限制塞入整个滑窗
# ------------------------------------------------------------
async def reason(state: AgentState) -> AgentState:
    messages = [{"role": "system", "content": _build_system_prompt(state)}]
    history = fit_history(short_term_store.history(state["session_id"]), settings.history_token_budget)
    messages.extend(history)
    messages.append({"role": "user", "content": state["message"]})

    resp = await _llm.ainvoke(messages)
    return {"reply": resp.content}


# ------------------------------------------------------------
# Node 3: store_memory —— LLM 抽取结构化事实, 回写画像与向量记忆
# ------------------------------------------------------------
async def store_memory(state: AgentState) -> AgentState:
    msg = state["message"].strip()
    if not _worth_storing(msg):  # 廉价预筛, 寒暄不惊动 LLM
        return {"stored": _empty_facts()}

    facts = await extract_facts(msg, state.get("reply", ""), state.get("profile"))
    await _persist_facts(state["user_id"], state.get("session_id", ""), facts)
    return {"stored": facts}


async def _persist_facts(user_id: str, session_id: str, facts: dict) -> None:
    """把抽取出的事实分发到三层记忆：画像 → SQLite，记忆 → ChromaDB。"""
    if facts["profile"]:
        await structured.update_profile(user_id, **facts["profile"])

    for pref in facts["preferences"]:
        await structured.update_preference(user_id, pref["key"], pref["value"])

    for item in facts["memories"]:
        long_term.add_memory(
            user_id=user_id,
            text=item["text"],
            metadata={"session_id": session_id, "source": "extracted"},
            importance=item["importance"],
        )


# ============================================================
# 内部辅助
# ============================================================
def _worth_storing(msg: str) -> bool:
    """简单而实用的存储启发式：过短或纯寒暄不存。"""
    if len(msg) < 6:
        return False
    if msg.lower() in _TRIVIAL:
        return False
    return True


def _empty_facts() -> dict:
    return {"profile": {}, "preferences": [], "memories": []}


def _build_system_prompt(state: AgentState) -> str:
    profile = state.get("profile") or {}
    retrieved = state.get("retrieved") or []

    lines = [
        "你是一位贴心的研究助手，专门帮助研究生管理论文阅读记录、研究偏好与历史讨论。",
        "你具备跨会话的长期记忆，应自然地利用下方记忆，让用户感到你越来越懂他。",
    ]

    if profile:
        lines.append("\n[用户画像]")
        if profile.get("name"):
            lines.append(f"- 姓名: {profile['name']}")
        if profile.get("research_domain"):
            lines.append(f"- 研究领域: {profile['research_domain']}")
        for k, v in (profile.get("preferences") or {}).items():
            lines.append(f"- 偏好 {k}: {v['value']}")

    if retrieved:
        lines.append("\n[相关长期记忆] (按重要性排序, 已含时间衰减)")
        for m in retrieved:
            lines.append(f"- {m['text']}")

    lines.append("\n请用简洁、专业且友好的语气回答。")
    return "\n".join(lines)
