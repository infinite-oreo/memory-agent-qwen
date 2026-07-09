/**
 * [INPUT]: 依赖 react 的 useState/useRef/useEffect，依赖 api/client.chat，依赖 MessageBubble
 * [OUTPUT]: 对外提供 ChatWindow 组件 (props: userId, sessionId, onReply)
 * [POS]: components 的对话主界面，驱动一问一答并上报已用记忆
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useEffect, useRef, useState } from "react";
import { chat, ChatResponse } from "../api/client";
import MessageBubble, { ChatMessage } from "./MessageBubble";

interface Props {
  userId: string;
  sessionId: string;
  onReply: (res: ChatResponse) => void;
}

export default function ChatWindow({ userId, sessionId, onReply }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    try {
      const res = await chat(userId, text, sessionId);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      onReply(res);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `⚠️ 出错了：${(err as Error).message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">开始和你的研究助手对话吧，它会记住你 👋</div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} content={m.content} />
        ))}
        {loading && <div className="chat-typing">助手思考中…</div>}
        <div ref={endRef} />
      </div>

      <div className="chat-input-bar">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="输入消息，Enter 发送 / Shift+Enter 换行"
          rows={2}
        />
        <button onClick={send} disabled={loading}>
          发送
        </button>
      </div>
    </div>
  );
}
