/**
 * API 客户端
 * ==========
 * 封装对后端 FastAPI 的所有 HTTP 请求。
 *
 * 设计要点：
 * - 自动附加 JWT Token 到 Authorization 头
 * - 401 时自动清除 token 并跳转登录
 * - 统一错误处理
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// 内存中存储 token（也可用 localStorage）
let authToken: string | null = null;

export function setToken(token: string | null) {
  authToken = token;
  if (token) localStorage.setItem("auth_token", token);
  else localStorage.removeItem("auth_token");
}

export function getToken(): string | null {
  if (!authToken) {
    authToken = localStorage.getItem("auth_token");
  }
  return authToken;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // 401 → 清除 token，跳转登录
  if (res.status === 401) {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
      window.location.href = "/login";
    }
    throw new Error("未登录或登录已过期");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as any).detail || `请求失败 (${res.status})`);
  }

  return res.json();
}

// ---- Auth APIs ----

export const authAPI = {
  register: (data: { email: string; password: string; display_name: string }) =>
    request<{ user: any; token: { access_token: string } }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getMe: () => request<{ id: string; email: string; display_name: string; role: string }>("/users/me"),
};

// ---- Chat APIs ----

export const chatAPI = {
  createSession: (title: string) =>
    request<{ id: string }>("/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),

  getSessions: () =>
    request<any[]>("/chat/sessions"),

  getSession: (id: string) =>
    request<any>(`/chat/sessions/${id}`),

  sendMessage: (sessionId: string, content: string, model?: string) =>
    request<any>(`/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, model }),
    }),

  /** SSE 流式消息 */
  streamMessage: async function* (sessionId: string, content: string, model?: string) {
    const token = getToken();
    const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ content, model }),
    });
    if (!res.ok) throw new Error("Stream failed");
    const reader = res.body?.getReader();
    if (!reader) throw new Error("No stream body");
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") return;
          try { yield JSON.parse(data); } catch {}
        }
      }
    }
  },

  renameSession: (sessionId: string, title: string) =>
    request<any>(`/chat/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  deleteSession: (sessionId: string) =>
    request<any>(`/chat/sessions/${sessionId}`, { method: "DELETE" }),
};

// ---- Agent API ----

export const agentAPI = {
  chat: (content: string) =>
    request<any>("/agent/chat", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};

// ---- Code API ----

export const codeAPI = {
  submit: (code: string, exerciseId?: string, stdin?: string) =>
    request<any>("/code/submit", {
      method: "POST",
      body: JSON.stringify({ code, exercise_id: exerciseId, stdin: stdin || "" }),
    }),

  analyze: (code: string, stderr: string) =>
    request<{ explanation: string; concepts: string[] }>("/code/analyze", {
      method: "POST",
      body: JSON.stringify({ code, stderr }),
    }),
};

// ---- Exercise API ----

export const exerciseAPI = {
  list: (difficulty?: number, concepts?: string) => {
    const params = new URLSearchParams();
    if (difficulty) params.set("difficulty", String(difficulty));
    if (concepts) params.set("concepts", concepts);
    return request<any[]>(`/exercises?${params}`);
  },

  generate: (data: { concepts?: string; difficulty: number; count?: number }) =>
    request<any>("/exercises/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  get: (id: string) => request<any>(`/exercises/${id}`),

  submit: (id: string, code: string) =>
    request<any>(`/exercises/${id}/submit`, {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
};

// ---- Profile API ----

export const profileAPI = {
  get: () => request<any>("/profile/me"),
  weaknesses: () => request<any[]>("/profile/me/weaknesses"),
  recommendations: () => request<any>("/profile/me/recommendations"),
};
