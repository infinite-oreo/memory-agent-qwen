# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 fastapi.Header/HTTPException，依赖 memory.structured.verify_api_key
[OUTPUT]: 对外提供 extract_bearer_key / require_api_key
[POS]: api 模块的鉴权中枢，被 memory.py/user.py 挂载；chat.py 因 user_id 在请求体中另有本地依赖
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from fastapi import Header, HTTPException

from memory import structured


def extract_bearer_key(authorization: str | None) -> str:
    """从 Authorization: Bearer <key> 中取出 key；缺失或格式错误 → 401。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")
    return authorization.split(" ", 1)[1].strip()


async def require_api_key(
    user_id: str, authorization: str | None = Header(default=None)
) -> str:
    """
    路径参数版鉴权依赖：适用于 URL 中带 {user_id} 的路由。
    FastAPI 会把路由的 user_id 路径参数自动绑定到本依赖的同名形参。
    校验不通过（key 缺失/用户不存在/key 不匹配）统一 403，避免用户名枚举。
    """
    api_key = extract_bearer_key(authorization)
    if not await structured.verify_api_key(user_id, api_key):
        raise HTTPException(status_code=403, detail="invalid credentials")
    return user_id
