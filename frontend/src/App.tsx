/**
 * [INPUT]: 依赖 react 的 useState/useEffect，依赖 ChatWindow/MemoryPanel，依赖 api/client.createUser
 * [OUTPUT]: 对外提供 App 根组件
 * [POS]: frontend 的布局总成，左对话右记忆，统管 user/session 身份
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useEffect, useState } from "react";
import ChatWindow from "./components/ChatWindow";
import MemoryPanel from "./components/MemoryPanel";
import { createUser, ChatResponse, FactsLearned } from "./api/client";

// 演示用：固定 user，会话每次启动新建。生产应接入真实登录。
const USER_ID = "demo-user";
const SESSION_ID = `sess-${Date.now()}`;

// 本轮是否真有新习得（画像/偏好/记忆任一非空）
function hasLearned(f: FactsLearned): boolean {
  return (
    Object.keys(f.profile).length > 0 ||
    f.preferences.length > 0 ||
    f.memories.length > 0
  );
}

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [memoriesUsed, setMemoriesUsed] = useState<string[]>([]);
  const [learned, setLearned] = useState<FactsLearned | null>(null);

  // 启动即确保用户存在（幂等）
  useEffect(() => {
    createUser(USER_ID, "研究生小黄", "自然语言处理", "zh").catch(() => void 0);
  }, []);

  function handleReply(res: ChatResponse) {
    setMemoriesUsed(res.memories_used);
    setLearned(res.facts_learned);
    setRefreshKey((k) => k + 1); // 触发记忆面板刷新
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>MemoryAgent · 研究助手</h1>
        <span className="subtitle">越用越懂你的三层记忆 Agent</span>
      </header>

      <main className="app-main">
        <div className="chat-col">
          <ChatWindow
            userId={USER_ID}
            sessionId={SESSION_ID}
            onReply={handleReply}
          />
          {learned && hasLearned(learned) && (
            <div className="learned-banner">
              <strong>🆕 刚刚学到：</strong>
              <ul>
                {Object.entries(learned.profile).map(([k, v]) => (
                  <li key={`p-${k}`}>画像 · {k}：{v}</li>
                ))}
                {learned.preferences.map((p, i) => (
                  <li key={`pref-${i}`}>偏好 · {p.key}：{p.value}</li>
                ))}
                {learned.memories.map((m, i) => (
                  <li key={`m-${i}`}>记忆 · {m}</li>
                ))}
              </ul>
            </div>
          )}

          {memoriesUsed.length > 0 && (
            <div className="used-memories">
              <strong>本轮调用的记忆：</strong>
              <ul>
                {memoriesUsed.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <MemoryPanel userId={USER_ID} refreshKey={refreshKey} />
      </main>
    </div>
  );
}
