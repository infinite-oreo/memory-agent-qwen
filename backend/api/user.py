# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 fastapi.APIRouter，依赖 memory.structured 的 create_user/update_preference/get_user_profile
[OUTPUT]: 对外提供 router (POST /user, PUT /user/{user_id}/preference, GET /user/{user_id})
[POS]: api 模块的用户画像入口，管理结构化身份与偏好
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from memory import structured

router = APIRouter(tags=["user"])


class CreateUserRequest(BaseModel):
    user_id: str
    name: str = ""
    research_domain: str = ""
    language_preference: str = "zh"


class PreferenceRequest(BaseModel):
    key: str
    value: str


@router.post("/user")
async def create_user(req: CreateUserRequest) -> dict:
    """创建或更新用户基本画像（幂等）。"""
    return await structured.create_user(
        req.user_id, req.name, req.research_domain, req.language_preference
    )


@router.get("/user/{user_id}")
async def get_user(user_id: str) -> dict:
    profile = await structured.get_user_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="user not found")
    return profile


@router.put("/user/{user_id}/preference")
async def set_preference(user_id: str, req: PreferenceRequest) -> dict:
    """写入/更新单条偏好。"""
    return await structured.update_preference(user_id, req.key, req.value)
