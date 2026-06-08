"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoading, error } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await login(email, password); router.push("/"); } catch {}
  };

  return (
    <div className="min-h-[calc(100vh-56px)] flex">
      {/* 左侧品牌区 */}
      <div className="hidden lg:flex w-[480px] bg-gradient-to-br from-indigo-600 via-violet-600 to-purple-700 flex-col justify-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-10 w-72 h-72 bg-white rounded-full blur-3xl" />
          <div className="absolute bottom-10 right-10 w-96 h-96 bg-purple-300 rounded-full blur-3xl" />
        </div>
        <div className="relative">
          <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center mb-8 shadow-lg">
            <span className="text-3xl">🐍</span>
          </div>
          <h1 className="text-4xl font-bold text-white mb-4 tracking-tight">欢迎回来</h1>
          <p className="text-lg text-indigo-200 leading-relaxed">
            继续你的 Python 学习之旅。<br/>AI 导师随时准备帮助你。
          </p>
        </div>
      </div>

      {/* 右侧表单区 */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">登录账号</h2>
            <p className="text-slate-500">输入你的邮箱和密码</p>
          </div>

          {error && (
            <div className="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl mb-6 text-sm flex items-center gap-2">
              <span className="text-base">⚠</span> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">邮箱地址</label>
              <input type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
                placeholder="your@email.com" />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">密码</label>
              <input type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
                placeholder="••••••••" />
            </div>

            <button type="submit" disabled={isLoading}
              className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-3 rounded-xl font-medium hover:from-indigo-700 hover:to-violet-700 disabled:opacity-50 transition-all shadow-sm shadow-indigo-200">
              {isLoading ? "登录中..." : "登录"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-8">
            还没有账号？<Link href="/register" className="text-indigo-600 font-medium hover:underline">立即注册 →</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
