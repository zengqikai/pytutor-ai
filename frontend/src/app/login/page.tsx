"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";

const features = [
  { icon: "🧠", title: "AI Tutor", desc: "DeepSeek 驱动的智能导师，实时解答 Python 问题，提供分层提示和代码审查" },
  { icon: "⚡", title: "Code Review", desc: "安全沙箱执行你的代码，AI 自动分析错误原因并给出改进建议" },
  { icon: "📊", title: "Learning Intelligence", desc: "追踪知识薄弱点，生成个性化练习，推荐最优学习路径" },
];

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
    <div className="min-h-[calc(100vh-56px)] flex relative overflow-hidden">
      {/* 左侧品牌区 */}
      <div className="hidden lg:flex w-[520px] flex-col justify-center px-14 relative bg-[#0a0a1e]">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-1/4 left-1/4 w-80 h-80 bg-indigo-600/15 rounded-full blur-[100px]" />
          <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-violet-600/10 rounded-full blur-[80px]" />
          <div className="absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px)", backgroundSize: "60px 60px" }} />
        </div>
        <div className="relative space-y-10">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold shadow-xl shadow-indigo-500/25">Py</div>
            <span className="text-2xl font-bold text-white tracking-tight">PyTutor</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white leading-tight mb-3">
              你的 AI Python<br/>编程导师
            </h1>
            <p className="text-slate-400 leading-relaxed">
              基于深度学习的个性化编程学习平台。<br/>
              智能对话、代码审查、知识追踪——一站式掌握 Python。
            </p>
          </div>
          <div className="space-y-4">
            {features.map((f) => (
              <div key={f.title} className="flex gap-4 p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-colors">
                <span className="text-2xl flex-shrink-0">{f.icon}</span>
                <div>
                  <p className="font-semibold text-white text-sm">{f.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 右侧登录表单 */}
      <div className="flex-1 flex items-center justify-center p-8 bg-[#06060f]">
        <div className="w-full max-w-md">
          <div className="glass rounded-2xl p-8 animate-fade-in">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-white mb-2">欢迎回来</h2>
              <p className="text-slate-400 text-sm">继续你的 AI Python 学习旅程</p>
            </div>

            {error && (
              <div className="bg-rose-500/10 border border-rose-500/20 text-rose-300 px-4 py-3 rounded-xl mb-6 text-sm">{error}</div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">邮箱地址</label>
                <input type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="neon w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition-all"
                  placeholder="your@email.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">密码</label>
                <input type="password" required value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="neon w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition-all"
                  placeholder="••••••••" />
              </div>
              <button type="submit" disabled={isLoading}
                className="glow-hover w-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-3 rounded-xl font-medium
                  hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40 transition-all text-sm">
                {isLoading ? "登录中..." : "登录"}
              </button>
            </form>

            <p className="text-center text-sm text-slate-500 mt-8">
              还没有账号？<Link href="/register" className="text-indigo-400 font-medium hover:text-indigo-300 transition-colors">创建账号 →</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
