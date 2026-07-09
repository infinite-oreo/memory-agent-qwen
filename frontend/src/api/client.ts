/**
 * [INPUT]: 依赖 fetch，依赖 import.meta.env.VITE_API_BASE (默认 /api)
 * [OUTPUT]: 对外提供 chat / getMemory / createUser 及相关类型
 * [POS]: frontend/api 的唯一后端通信封装，组件不直接碰 fetch
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

// 开发时经 Vite 代理走 /api → localhost:8000；生产可用 VITE_API_BASE 覆盖
const BASE = (import.meta.env.VITE_API_BASE as string) || "/api";

export interface FactsLearned {
  profile: Record<string, string>;
  preferences: { key: string; value: string }[];
  memories: string[];
}

export interface ChatResponse {
  reply: string;
  memories_used: string[];
  facts_learned: FactsLearned;
}

export interface MemoryItem {
  id: string;
  text: string;
  created_at: string;
  last_access: string;
  access_count: number;
}

export interface MemoryView {
  user_id: string;
  profile: Record<string, unknown> | null;
  memories: MemoryItem[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function chat(
  userId: string,
  message: string,
  sessionId: string
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, message, session_id: sessionId }),
  });
}

export function getMemory(userId: string): Promise<MemoryView> {
  return request<MemoryView>(`/memory/${encodeURIComponent(userId)}`);
}

export function createUser(
  userId: string,
  name = "",
  researchDomain = "",
  languagePreference = "zh"
): Promise<unknown> {
  return request("/user", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      name,
      research_domain: researchDomain,
      language_preference: languagePreference,
    }),
  });
}
