# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 fastapi/uvicorn，依赖 api.{chat,memory,user}.router，依赖 memory.structured.init_db
[OUTPUT]: 对外提供 app (FastAPI 实例) 与 __main__ 启动入口
[POS]: backend 的进程入口，组装 CORS、生命周期与全部路由
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from memory.structured import init_db
from api.chat import router as chat_router
from api.memory import router as memory_router
from api.user import router as user_router


# ============================================================
# 生命周期 —— 启动时建表, 让结构化记忆就绪
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="MemoryAgent · Qwen",
    description="具备三层持久记忆架构的研究助手 Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# ---- CORS：放行前端开发服务器 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 路由装配 ----
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(user_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": settings.qwen_model}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
