# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 fastapi.APIRouter，依赖 agent.graph.run_agent，依赖 api.auth.extract_bearer_key，依赖 memory.structured.verify_api_key
[OUTPUT]: 对外提供 router (POST /chat，鉴权：Authorization: Bearer <api_key> 须匹配 body.user_id)
[POS]: api 模块的对话入口，连接前端与 Agent 认知流
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from agent.graph import run_agent
from api.auth import extract_bearer_key
from memory import structured

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str


class MemoryFact(BaseModel):
    text: str
    importance: float = 0.5
    memory_type: str = "semantic"


class FactsLearned(BaseModel):
    profile: dict = {}
    preferences: list[dict] = []
    memories: list[MemoryFact] = []


class ChatResponse(BaseModel):
    reply: str
    memories_used: list[str]
    facts_learned: FactsLearned = FactsLearned()


async def require_chat_api_key(
    req: ChatRequest, authorization: str | None = Header(default=None)
) -> str:
    """
    body 参数版鉴权依赖：user_id 在请求体而非路径中，故不能复用 api.auth.require_api_key。
    FastAPI 支持依赖函数与路由声明同一个 Pydantic body 模型，请求体会被分别解析注入两处。
    """
    api_key = extract_bearer_key(authorization)
    if not await structured.verify_api_key(req.user_id, api_key):
        raise HTTPException(status_code=403, detail="invalid credentials")
    return req.user_id


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, _: str = Depends(require_chat_api_key)) -> ChatResponse:
    """单轮对话：检索记忆 → 推理 → 存储 → 返回回复与所用记忆。"""
    result = await run_agent(req.user_id, req.message, req.session_id)
    return ChatResponse(**result)
