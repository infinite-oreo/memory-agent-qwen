# MemoryAgent · Qwen —— 越用越懂你的研究助手

一个具备**三层持久记忆架构**的 AI Agent，能跨会话记住用户的身份、研究偏好与历史讨论。
面向研究生场景：帮你记住论文阅读记录、研究方向偏好、过往讨论上下文。

> Qwen Cloud 全球 AI 黑客马拉松 · MemoryAgent 赛道作品

---

## ✨ 核心特性

- **三层记忆架构**
  - 🟢 **短期记忆**（in-memory）：会话内对话滑窗，进程内有效
  - 🔵 **长期记忆**（ChromaDB 向量库）：跨会话语义记忆，多语言 embedding
  - 🟡 **结构化画像**（SQLite）：姓名 / 研究领域 / 偏好键值
- **遗忘机制**：`score = 语义相似度 × exp(-λ × 距上次访问天数)`，检索时重排，模拟人类记忆的时间衰减
- **认知流编排**：LangGraph 串联 `检索记忆 → 推理 → 存储` 单向状态流
- **记忆可视化**：前端右侧面板实时展示"Agent 现在记住了什么"
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
| `QWEN_API_KEY` | Qwen Cloud API Key（**必填**，经 [qwencloud-getapi](https://bit.ly/qwencloud-getapi) 申请，国际版 key，与国内百炼 key 不通用） | — |
| `QWEN_BASE_URL` | OpenAI 兼容端点（国际版，官方指定，勿改回国内 `dashscope.aliyuncs.com`） | `dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `QWEN_MODEL` | 对话模型 | `qwen-max` |
| `CHROMA_DIR` | 向量库持久化目录 | `./chroma_db` |
| `SQLITE_PATH` | 用户画像数据库 | `./profiles.db` |
| `EMBED_MODEL` | embedding 模型 | `paraphrase-multilingual-MiniLM-L12-v2` |
| `FORGETTING_LAMBDA` | 遗忘衰减系数 λ | `0.01` |
| `RETRIEVE_TOP_K` | 每次召回记忆条数 | `5` |
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

MIT © 2026 Jacky Huang
