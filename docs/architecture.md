# MemoryAgent 架构说明

## 1. 设计哲学

> 让数据如河流般单向流动；让记忆如生命般自然衰减。

人类之所以"越用越懂"，不在于记住一切，而在于**有选择地记住、有衰减地遗忘、有相关地唤起**。
本系统将这一认知规律具现为三层记忆 + 一条单向认知流。

## 2. 三层记忆架构

| 层 | 载体 | 生命周期 | 职责 |
|----|------|----------|------|
| 短期记忆 | 进程内 `deque` | 会话级（重启即失） | 维持当前对话连贯性 |
| 长期记忆 | ChromaDB 向量库 | 永久（磁盘持久化） | 跨会话语义记忆，可被相似度唤起 |
| 结构化画像 | SQLite | 永久 | 稳定事实：姓名 / 领域 / 偏好 |

向量记忆负责"模糊的、语义的"回忆；结构化画像负责"精确的、事实的"身份。
二者互补，共同拼成 system prompt 注入推理。

## 3. 认知流（LangGraph）

```
START
  │
  ▼
retrieve_memory   ← 从 ChromaDB 语义召回 + SQLite 读画像 + 遗忘重排
  │
  ▼
reason            ← 拼装 [画像 + 长期记忆 + 短期历史 + 当前消息] → Qwen 生成
  │
  ▼
store_memory      ← 廉价预筛 → LLM 抽取结构化事实 → 回写画像/向量记忆
  │
  ▼
END  → { reply, memories_used, facts_learned }
```

状态 `AgentState` 在节点间单向流动，每个节点只产出增量字段，符合"单一真相源 + 不可变流"原则。

### store_memory：从「存原话」到「提炼事实」

`store_memory` 不再原样存储用户话语，而是经 `memory/extractor.py` 做一次
**temperature=0 的结构化抽取**，把对话蒸馏为三类可回写实体：

```
extract_facts(user_msg, reply, profile)
   → { profile:      {name, research_domain, language_preference},   # → SQLite (update_profile 部分更新)
       preferences:  [{key, value}, ...],                            # → SQLite (update_preference upsert)
       memories:     ["第三人称事实陈述", ...] }                      # → ChromaDB (add_memory)
```

设计要点：

- **廉价预筛先行**：寒暄/过短消息不惊动 LLM（`_worth_storing`），实用主义对抗无谓开销。
- **抽取与对话分离**：抽取用独立的 0 温度 LLM 实例，确定性优先；对话用 0.7 温度，创造性优先。
- **容错降级**：JSON 解析失败或 LLM 异常一律降级为空结果，存储是锦上添花，绝不阻断对话主流程。
- **部分更新不误伤**：`update_profile` 只写抽到的非空字段，用户不存在时自动建壳（upsert）。
- **抽取可见**：`facts_learned` 经 `/chat` 透传前端，实时展示"Agent 刚刚学到了什么"。

记忆从此存的是用户**是谁、要什么**，而非用户**说了什么** —— 这是"越用越懂"的物质基础。

## 4. 遗忘机制

检索得到的候选记忆按下式重排：

```
decayed_score = semantic_similarity × exp(-λ × days_since_last_access)
```

- `λ`（`FORGETTING_LAMBDA`，默认 0.01）控制遗忘速度
- 命中即"强化"：刷新 `last_access`、累加 `access_count`，常被唤起的记忆衰减更慢

这让系统天然偏好"既相关、又新鲜/常用"的记忆，避免陈旧信息淹没上下文。

## 5. 模块依赖关系

```
api/chat ──► agent/graph ──► agent/nodes ──┬─► memory/long_term ──► memory/forgetting
                                           ├─► memory/structured
                                           └─► memory/short_term
api/memory ─► memory/long_term + memory/structured
api/user ───► memory/structured
config ◄──── (被所有层读取)
```

## 6. 部署拓扑

```
[浏览器] ──► Nginx(前端:5173) ──/api──► FastAPI(后端:8000)
                                          ├─ ChromaDB (volume:/data/chroma_db)
                                          └─ SQLite   (volume:/data/profiles.db)
```

docker-compose 编排前后端两服务，记忆数据通过命名卷 `memory-data` 持久化，
容器重建不丢记忆 —— 这是"持久记忆"承诺的物理保证。

## 7. 演化方向

- ✅ ~~store_memory 由启发式升级为 LLM 抽取（结构化抽取 fact / preference 自动回写 SQLite）~~（已实现，见 §3）
- 长期记忆去重：add_memory 前做相似度比对，避免同一事实反复入库
- 长期记忆引入分类（episodic / semantic / procedural）
- 多用户鉴权与会话历史持久化
- 遗忘机制引入"重要性"权重，而非纯时间衰减
