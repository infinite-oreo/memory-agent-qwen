/**
 * [INPUT]: 依赖 react 的 useState/useEffect/useCallback，依赖 api/client.getMemory
 * [OUTPUT]: 对外提供 MemoryPanel 组件 (props: userId, refreshKey)
 * [POS]: components 的右侧记忆面板，可视化 Agent "记住了什么"
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useCallback, useEffect, useState } from "react";
import { getMemory, MemoryView } from "../api/client";

interface Props {
  userId: string;
  refreshKey: number; // 每次对话后变更, 触发刷新
}

function fmt(ts: string): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString("zh-CN");
}

export default function MemoryPanel({ userId, refreshKey }: Props) {
  const [view, setView] = useState<MemoryView | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setView(await getMemory(userId));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const profile = view?.profile as Record<string, any> | null;

  return (
    <aside className="memory-panel">
      <h2>🧠 Agent 记忆</h2>

      <section className="profile-box">
        <h3>用户画像</h3>
        {profile ? (
          <ul>
            <li>姓名：{profile.name || "—"}</li>
            <li>研究领域：{profile.research_domain || "—"}</li>
            <li>语言偏好：{profile.language_preference || "—"}</li>
          </ul>
        ) : (
          <p className="muted">尚无画像</p>
        )}
      </section>

      <section>
        <h3>长期记忆（{view?.memories.length ?? 0}）</h3>
        {error && <p className="error">加载失败：{error}</p>}
        {view && view.memories.length === 0 && (
          <p className="muted">还没有记住任何内容</p>
        )}
        <ul className="memory-list">
          {view?.memories.map((m) => (
            <li key={m.id} className="memory-item">
              <div className="memory-text">{m.text}</div>
              <div className="memory-meta">
                <span>存于 {fmt(m.created_at)}</span>
                <span>· 访问 {m.access_count} 次</span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
