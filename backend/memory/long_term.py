# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 chromadb 持久化客户端，依赖 sentence-transformers 嵌入函数，依赖 forgetting.rerank_by_forgetting
[OUTPUT]: 对外提供 add_memory / retrieve_memory / list_memories
[POS]: memory 模块的长期向量记忆，Agent 跨会话语义记忆的物质载体
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import uuid
from datetime import datetime, timezone

import chromadb
from chromadb.utils import embedding_functions

from config import settings
from memory.forgetting import rerank_by_forgetting

# ============================================================
# ChromaDB 单例 —— 本地持久化，进程内唯一向量库
#   embedding 用多语言 MiniLM，中文语义不失真
# ============================================================
_client = chromadb.PersistentClient(path=settings.chroma_dir)
_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=settings.embed_model
)
_collection = _client.get_or_create_collection(
    name="long_term_memory",
    embedding_function=_embed_fn,
    metadata={"hnsw:space": "cosine"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_memory(user_id: str, text: str, metadata: dict | None = None) -> str:
    """
    写入一条长期记忆。
    metadata 自动注入 user_id / created_at / last_access / access_count。
    返回记忆 id。
    """
    mem_id = str(uuid.uuid4())
    meta = dict(metadata or {})
    now = _now()
    meta.update(
        {
            "user_id": user_id,
            "created_at": meta.get("created_at", now),
            "last_access": now,
            "access_count": int(meta.get("access_count", 0)),
        }
    )
    _collection.add(ids=[mem_id], documents=[text], metadatas=[meta])
    return mem_id


def retrieve_memory(user_id: str, query: str, top_k: int | None = None) -> list[dict]:
    """
    语义检索 + 遗忘重排。
    返回 [{id, text, metadata, similarity, decayed_score}, ...]，
    并对命中记忆原地更新 last_access / access_count（强化被唤起的记忆）。
    """
    k = settings.retrieve_top_k if top_k is None else top_k

    # 先看该用户是否有记忆，避免空集合查询报错
    existing = _collection.get(where={"user_id": user_id}, include=[])
    if not existing["ids"]:
        return []

    res = _collection.query(
        query_texts=[query],
        n_results=min(k * 2, len(existing["ids"])),  # 多召回, 给遗忘重排留空间
        where={"user_id": user_id},
        include=["documents", "metadatas", "distances"],
    )

    memories: list[dict] = []
    for mid, doc, meta, dist in zip(
        res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        memories.append(
            {
                "id": mid,
                "text": doc,
                "metadata": meta,
                "similarity": 1.0 - dist,  # cosine distance -> similarity
            }
        )

    ranked = rerank_by_forgetting(memories)[:k]
    _reinforce([m["id"] for m in ranked])
    return ranked


def _reinforce(mem_ids: list[str]) -> None:
    """命中即强化：刷新 last_access，累加 access_count。"""
    if not mem_ids:
        return
    got = _collection.get(ids=mem_ids, include=["metadatas"])
    now = _now()
    new_metas = []
    for meta in got["metadatas"]:
        meta = dict(meta)
        meta["last_access"] = now
        meta["access_count"] = int(meta.get("access_count", 0)) + 1
        new_metas.append(meta)
    _collection.update(ids=got["ids"], metadatas=new_metas)


def list_memories(user_id: str) -> list[dict]:
    """列出某用户全部长期记忆（供前端记忆面板展示），按创建时间倒序。"""
    got = _collection.get(where={"user_id": user_id}, include=["documents", "metadatas"])
    items = [
        {"id": mid, "text": doc, "metadata": meta}
        for mid, doc, meta in zip(got["ids"], got["documents"], got["metadatas"])
    ]
    items.sort(key=lambda x: x["metadata"].get("created_at", ""), reverse=True)
    return items
