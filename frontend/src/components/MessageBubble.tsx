/**
 * [INPUT]: 依赖 react、react-markdown，消费 props: { role, content }
 * [OUTPUT]: 对外提供 MessageBubble 组件 与 ChatMessage 类型
 * [POS]: components 的最小展示原子，被 ChatWindow 渲染消息列表时复用
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import ReactMarkdown from "react-markdown";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function MessageBubble({ role, content }: ChatMessage) {
  const isUser = role === "user";
  return (
    <div className={`bubble-row ${isUser ? "right" : "left"}`}>
      <div className={`bubble ${isUser ? "bubble-user" : "bubble-assistant"}`}>
        {isUser ? content : <ReactMarkdown>{content}</ReactMarkdown>}
      </div>
    </div>
  );
}
