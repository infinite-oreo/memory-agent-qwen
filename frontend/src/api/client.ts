/**
 * [INPUT]: 依赖 fetch，依赖 import.meta.env.VITE_API_BASE (默认 /api)，依赖 localStorage 持久化 api_key
 * [OUTPUT]: 对外提供 chat / getMemory / createUser 及相关类型；request() 自动附带 Authorization: Bearer <api_key>
 * [POS]: frontend/api 的唯一后端通信封装，组件不直接碰 fetch
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

// 开发时经 Vite 代理走 /api → localhost:8000；生产可用 VITE_API_BASE 覆盖
const BASE = (import.meta.env.VITE_API_BASE as string) || "/api";

// 后端签发的 api_key 落盘于此；createUser() 首次调用后写入，request() 每次请求自动附带
const API_KEY_STORAGE_KEY = "memoryagent_api_key";

function getStoredApiKey(): string | null {
  return localStorage.getItem(API_KEY_STORAGE_KEY);
}

export interface MemoryFact {
  text: string;
  importance: number;
  memory_type: string;
}

export interface FactsLearned {
  profile: Record<string, string>;
  preferences: { key: string; value: string }[];
  memories: MemoryFact[];
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
  importance: number;
  memory_type: string;
}

export interface MemoryView {
  user_id: string;
  profile: Record<string, unknown> | null;
  memories: MemoryItem[];
}

export interface UserProfile {
  user_id: string;
  name: string;
  research_domain: string;
  language_preference: string;
  api_key: string;
  preferences: Record<string, { value: string; updated_at: string }>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = getStoredApiKey();
  if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;

  const res = await fetch(`${BASE}${path}`, { headers, ...init });
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

export async function createUser(
  userId: string,
  name = "",
  researchDomain = "",
  languagePreference = "zh"
): Promise<UserProfile> {
  const profile = await request<UserProfile>("/user", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      name,
      research_domain: researchDomain,
      language_preference: languagePreference,
    }),
  });
  if (profile.api_key) {
    localStorage.setItem(API_KEY_STORAGE_KEY, profile.api_key);
  }
  return profile;
}
