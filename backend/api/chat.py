# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 fastapi.APIRouter，依赖 agent.graph.run_agent
[OUTPUT]: 对外提供 router (POST /chat)
[POS]: api 模块的对话入口，连接前端与 Agent 认知流
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from fastapi import APIRouter
from pydantic import BaseModel

from agent.graph import run_agent

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str


class MemoryFact(BaseModel):
    text: str
    importance: float = 0.5


class FactsLearned(BaseModel):
    profile: dict = {}
    preferences: list[dict] = []
    memories: list[MemoryFact] = []


class ChatResponse(BaseModel):
    reply: str
    memories_used: list[str]
    facts_learned: FactsLearned = FactsLearned()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """单轮对话：检索记忆 → 推理 → 存储 → 返回回复与所用记忆。"""
    result = await run_agent(req.user_id, req.message, req.session_id)
    return ChatResponse(**result)
