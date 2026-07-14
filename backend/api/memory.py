# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 fastapi.APIRouter，依赖 memory.long_term.list_memories，依赖 memory.structured.get_user_profile
[OUTPUT]: 对外提供 router (GET /memory/{user_id})
[POS]: api 模块的记忆查询入口，为前端记忆面板供数据
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from fastapi import APIRouter
from pydantic import BaseModel

from memory import long_term, structured

router = APIRouter(tags=["memory"])


class MemoryItem(BaseModel):
    id: str
    text: str
    created_at: str
    last_access: str
    access_count: int
    importance: float


class MemoryView(BaseModel):
    user_id: str
    profile: dict | None
    memories: list[MemoryItem]


@router.get("/memory/{user_id}", response_model=MemoryView)
async def get_memory(user_id: str) -> MemoryView:
    """返回某用户的结构化画像 + 全部长期记忆（含访问统计）。"""
    profile = await structured.get_user_profile(user_id)
    raw = long_term.list_memories(user_id)
    items = [
        MemoryItem(
            id=m["id"],
            text=m["text"],
            created_at=m["metadata"].get("created_at", ""),
            last_access=m["metadata"].get("last_access", ""),
            access_count=int(m["metadata"].get("access_count", 0)),
            importance=float(m["metadata"].get("importance", 0.5)),
        )
        for m in raw
    ]
    return MemoryView(user_id=user_id, profile=profile, memories=items)
