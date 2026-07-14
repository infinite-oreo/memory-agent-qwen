# MemoryAgent · Qwen —— 越用越懂你的研究助手

一个具备**三层持久记忆架构**的 AI Agent，能跨会话记住用户的身份、研究偏好与历史讨论。
面向研究生场景：帮你记住论文阅读记录、研究方向偏好、过往讨论上下文。

> Qwen Cloud 全球 AI 黑客马拉松 · MemoryAgent 赛道作品

---

## 📖 项目背景

本项目参加 **Global AI Hackathon Series with Qwen Cloud**（Devpost 主办）的 **MemoryAgent 赛道**，
赛道要求构建一个具备持久记忆的 Agent：自主积累经验、记住用户偏好，并在多轮、跨会话的交互中做出越来越准确的判断；
重点考察三件事——**高效的记忆存储与检索**、**及时遗忘过时信息**、**在有限上下文窗口内召回关键记忆**。

本项目正是围绕这三个考察点展开：三层记忆架构（短期/长期/结构化）+ 写入前去重负责高效存储与检索，
`memory/forgetting.py` 的重要性加权时间衰减 + 定期真删除负责及时遗忘，
`memory/context_budget.py` 的 token 预算裁剪负责在有限上下文窗口内精选最关键的记忆与历史。

---

## ✨ 核心特性

- **三层记忆架构**
  - 🟢 **短期记忆**（in-memory）：会话内对话滑窗，进程内有效
  - 🔵 **长期记忆**（ChromaDB 向量库）：跨会话语义记忆，多语言 embedding
  - 🟡 **结构化画像**（SQLite）：姓名 / 研究领域 / 偏好键值
- **遗忘机制**：`score = 语义相似度 × 重要性^α × exp(-λ × 距上次访问天数)`，检索时重排；跌破阈值的陈旧记忆定期真删除，而非只降权
- **记忆去重**：新记忆写入前做向量相似度查重，语义重复则强化旧记忆（刷新访问、重要性取高者）而非重复入库
- **重要性权重**：LLM 抽取记忆时同步打 0~1 重要性分，核心事实衰减更慢，一次性话题更快被遗忘
- **Token 预算上下文**：`tiktoken` 计数，长期记忆与短期历史按真实 token 预算动态裁剪注入 prompt，而非拍脑袋定条数
- **认知流编排**：LangGraph 串联 `检索记忆 → 推理 → 存储` 单向状态流
- **记忆可视化**：前端右侧面板实时展示"Agent 现在记住了什么"，含重要性标注
- **Qwen 接入**：通过 OpenAI 兼容接口调用 `qwen-max`

---

## 🏗️ 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python · FastAPI · LangGraph |
| LLM | Qwen Cloud（`qwen-max`，OpenAI 兼容接口） |
| 长期记忆 | ChromaDB + sentence-transformers（多语言 MiniLM） |
| 结构化记忆 | SQLite（aiosqlite 异步） |
| 前端 | React · TypeScript · Vite |
| 部署 | Docker · docker-compose · 阿里云 ECS |

---

## 🚀 本地运行

### 方式一：Docker（推荐，一键启动）

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env
#   编辑 backend/.env，至少填入 QWEN_API_KEY

# 2. 一键拉起前后端
docker compose up --build
```

- 前端： http://localhost:5173
- 后端 API： http://localhost:8000
- 接口文档（Swagger）： http://localhost:8000/docs

### 方式二：本地分别启动（开发调试）

**后端**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 QWEN_API_KEY
uvicorn main:app --reload --port 8000
```

**前端**

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

> 开发模式下，Vite 通过 `/api` 代理转发到后端 `localhost:8000`。

---

## ⚙️ 环境变量说明

复制 `backend/.env.example` 为 `backend/.env`，按需修改：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QWEN_API_KEY` | Qwen Cloud API Key（**必填**，经 [qwencloud-getapi](https://bit.ly/qwencloud-getapi) 申请，需为国际版 key） | — |
| `QWEN_BASE_URL` | OpenAI 兼容端点（国际版 `dashscope.aliyuncs.com`） | `dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `QWEN_MODEL` | 对话模型 | `qwen-max` |
| `CHROMA_DIR` | 向量库持久化目录 | `./chroma_db` |
| `SQLITE_PATH` | 用户画像数据库 | `./profiles.db` |
| `EMBED_MODEL` | embedding 模型 | `paraphrase-multilingual-MiniLM-L12-v2` |
| `FORGETTING_LAMBDA` | 遗忘衰减系数 λ | `0.01` |
| `FORGETTING_PRUNE_THRESHOLD` | 记忆强度低于此值即真删除 | `0.05` |
| `DEDUP_SIMILARITY_THRESHOLD` | 去重相似度阈值（余弦） | `0.92` |
| `MEMORY_CANDIDATE_POOL` | 检索候选池大小（重排前） | `20` |
| `MEMORY_TOKEN_BUDGET` | 长期记忆注入 prompt 的 token 预算 | `800` |
| `HISTORY_TOKEN_BUDGET` | 短期历史注入 prompt 的 token 预算 | `1500` |
| `CORS_ORIGINS` | 放行的前端来源（逗号分隔） | localhost:5173 |

---

## 📡 API 速览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat` | 对话：`{user_id, message, session_id}` → `{reply, memories_used}` |
| `GET` | `/memory/{user_id}` | 查看用户全部记忆与画像 |
| `POST` | `/user` | 创建 / 更新用户画像 |
| `PUT` | `/user/{user_id}/preference` | 写入单条偏好 |
| `GET` | `/health` | 健康检查 |

---

## 📁 项目结构

```
memory-agent-qwen/
├── backend/          FastAPI + LangGraph + 三层记忆
│   ├── agent/        认知编排（graph / nodes）
│   ├── memory/       short_term / long_term / structured / forgetting
│   └── api/          chat / memory / user 路由
├── frontend/         React + TS（对话界面 + 记忆面板）
├── docker/           Dockerfile.backend / .frontend / nginx.conf
├── docs/             架构说明
└── docker-compose.yml
```

详见 [`docs/architecture.md`](docs/architecture.md)。

---

## 📄 License

MIT © 2026
