/**
 * 认证状态管理（Zustand）
 * =========================
 * 管理用户登录状态、token、用户信息。
 *
 * Zustand 是轻量级状态管理库——比 Redux 简单很多。
 * 创建一个 store = 一个 hook，组件直接调用。
 */

import { create } from "zustand";
import { authAPI, setToken, getToken } from "@/lib/api";

interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: false,
  isAuthenticated: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const res = await authAPI.login({ email, password });
      setToken(res.access_token);
      set({ isAuthenticated: true, isLoading: false });
      // 登录后加载用户信息
      await get().loadUser();
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
      throw e;
    }
  },

  register: async (email, password, displayName) => {
    set({ isLoading: true, error: null });
    try {
      const res = await authAPI.register({
        email,
        password,
        display_name: displayName,
      });
      setToken(res.token.access_token);
      set({
        user: res.user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
      throw e;
    }
  },

  logout: () => {
    setToken(null);
    set({ user: null, isAuthenticated: false });
  },

  loadUser: async () => {
    if (!getToken()) return;
    try {
      const user = await authAPI.getMe();
      set({ user, isAuthenticated: true });
    } catch {
      set({ isAuthenticated: false });
    }
  },
}));
