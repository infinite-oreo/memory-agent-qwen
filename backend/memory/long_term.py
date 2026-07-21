# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 chromadb 持久化客户端，依赖 sentence-transformers 嵌入函数，依赖 forgetting.rerank_by_forgetting/retention_score
[OUTPUT]: 对外提供 add_memory(含 memory_type 分类) / retrieve_memory / list_memories / prune_forgotten
[POS]: memory 模块的长期向量记忆，Agent 跨会话语义记忆的物质载体
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import uuid
from datetime import datetime, timezone

import chromadb
from chromadb.utils import embedding_functions

from config import settings
from memory.forgetting import rerank_by_forgetting, retention_score

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


_MEMORY_TYPES = {"episodic", "semantic", "procedural"}


def add_memory(
    user_id: str,
    text: str,
    metadata: dict | None = None,
    importance: float = 0.5,
    memory_type: str = "semantic",
) -> str:
    """
    写入一条长期记忆；若与已有记忆语义高度相似，视为同一事实的再次印证，
    强化旧记忆（刷新访问、重要性取高者）而非重复入库。
    metadata 自动注入 user_id / created_at / last_access / access_count / importance / memory_type。
    memory_type ∈ episodic/semantic/procedural，非法值兜底为 semantic。
    返回记忆 id（新建或被强化的既有记忆）。
    """
    if memory_type not in _MEMORY_TYPES:
        memory_type = "semantic"

    dup = _find_similar(user_id, text, settings.dedup_similarity_threshold)
    if dup is not None:
        mem_id, _similarity = dup
        _merge_duplicate(mem_id, importance)
        return mem_id

    mem_id = str(uuid.uuid4())
    meta = dict(metadata or {})
    now = _now()
    meta.update(
        {
            "user_id": user_id,
            "created_at": meta.get("created_at", now),
            "last_access": now,
            "access_count": int(meta.get("access_count", 0)),
            "importance": float(importance),
            "memory_type": memory_type,
        }
    )
    _collection.add(ids=[mem_id], documents=[text], metadatas=[meta])
    return mem_id


def _find_similar(user_id: str, text: str, threshold: float) -> tuple[str, float] | None:
    """在该用户已有记忆中找语义最相似的一条；相似度达阈值则返回 (id, similarity)。"""
    existing = _collection.get(where={"user_id": user_id}, include=[])
    if not existing["ids"]:
        return None
    res = _collection.query(
        query_texts=[text], n_results=1, where={"user_id": user_id}, include=["distances"]
    )
    if not res["ids"][0]:
        return None
    similarity = 1.0 - res["distances"][0][0]
    return (res["ids"][0][0], similarity) if similarity >= threshold else None


def _merge_duplicate(mem_id: str, new_importance: float) -> None:
    """
    强化被再次印证的旧记忆：刷新访问、重要性取新旧较高者。
    刻意不接收/不更新 memory_type —— 去重合并的语义是"同一事实的再次印证"，
    事实本身的类别不该因一次新措辞而漂移；若分类结果前后不一致，更可能是
    抽取器的判断噪声，保留旧记忆已有的 memory_type 比跟随新证据更稳妥。
    """
    got = _collection.get(ids=[mem_id], include=["metadatas"])
    if not got["ids"]:
        return
    meta = dict(got["metadatas"][0])
    meta["last_access"] = _now()
    meta["access_count"] = int(meta.get("access_count", 0)) + 1
    meta["importance"] = max(float(meta.get("importance", 0.5)), new_importance)
    _collection.update(ids=[mem_id], metadatas=[meta])


def retrieve_memory(user_id: str, query: str, top_k: int | None = None) -> list[dict]:
    """
    先真遗忘（剪除衰减到阈值以下的陈旧记忆），再语义检索 + 遗忘重排。
    返回 [{id, text, metadata, similarity, decayed_score}, ...]，
    并对命中记忆原地更新 last_access / access_count（强化被唤起的记忆）。
    """
    prune_forgotten(user_id)
    k = settings.memory_candidate_pool if top_k is None else top_k

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


def prune_forgotten(user_id: str, threshold: float | None = None) -> int:
    """
    真遗忘：把"记忆强度"(重要性 × 时间衰减) 跌破阈值的陈旧记忆彻底删除，
    而不是像检索重排那样只降权、永远留在库里。返回被删除的条数。
    """
    thr = settings.forgetting_prune_threshold if threshold is None else threshold
    got = _collection.get(where={"user_id": user_id}, include=["metadatas"])
    stale_ids = [
        mid
        for mid, meta in zip(got["ids"], got["metadatas"])
        if retention_score(
            meta.get("last_access", ""),
            float(meta.get("importance", 0.5)),
            memory_type=meta.get("memory_type"),
        )
        < thr
    ]
    if stale_ids:
        _collection.delete(ids=stale_ids)
    return len(stale_ids)


def list_memories(user_id: str) -> list[dict]:
    """列出某用户全部长期记忆（供前端记忆面板展示），按创建时间倒序。"""
    got = _collection.get(where={"user_id": user_id}, include=["documents", "metadatas"])
    items = [
        {"id": mid, "text": doc, "metadata": meta}
        for mid, doc, meta in zip(got["ids"], got["documents"], got["metadatas"])
    ]
    items.sort(key=lambda x: x["metadata"].get("created_at", ""), reverse=True)
    return items
