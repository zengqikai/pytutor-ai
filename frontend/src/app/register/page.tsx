"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { register, isLoading, error } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await register(email, password, displayName); router.push("/"); } catch {}
  };

  return (
    <div className="min-h-[calc(100vh-56px)] flex relative overflow-hidden">
      {/* 左侧品牌区 —— 青色主题 */}
      <div className="hidden lg:flex w-[520px] flex-col justify-center px-14 relative bg-[#0a0a1e]">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-1/4 left-1/4 w-80 h-80 bg-cyan-600/15 rounded-full blur-[100px]" />
          <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-teal-600/10 rounded-full blur-[80px]" />
          <div className="absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px)", backgroundSize: "60px 60px" }} />
        </div>
        <div className="relative space-y-10">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center text-white font-bold shadow-xl shadow-cyan-500/25">Py</div>
            <span className="text-2xl font-bold text-white tracking-tight">PyTutor</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white leading-tight mb-3">
              开启你的<br/>AI 学习之旅
            </h1>
            <p className="text-slate-400 leading-relaxed">
              注册即可获得专属 AI 编程导师。<br/>
              智能对话、实时代码审查、个性化学习路径。
            </p>
          </div>
          <div className="space-y-4">
            {[
              { icon: "🚀", title: "即刻开始", desc: "30 秒注册，立即与 AI 导师对话" },
              { icon: "🎯", title: "个性化学习", desc: "AI 追踪你的知识薄弱点并自动生成练习" },
              { icon: "🛡️", title: "安全沙箱", desc: "在隔离环境中安全运行你的 Python 代码" },
            ].map((f) => (
              <div key={f.title} className="flex gap-4 p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
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

      {/* 右侧注册表单 */}
      <div className="flex-1 flex items-center justify-center p-8 bg-[#06060f]">
        <div className="w-full max-w-md">
          <div className="glass rounded-2xl p-8 animate-fade-in">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-white mb-2">创建账号</h2>
              <p className="text-slate-400 text-sm">加入 PyTutor，开始学习 Python</p>
            </div>

            {error && (
              <div className="bg-rose-500/10 border border-rose-500/20 text-rose-300 px-4 py-3 rounded-xl mb-6 text-sm">{error}</div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">显示名称</label>
                <input type="text" required value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="neon w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition-all"
                  placeholder="小明" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">邮箱地址</label>
                <input type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="neon w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition-all"
                  placeholder="your@email.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  密码 <span className="text-slate-500 font-normal">（8-72字符，含字母和数字）</span>
                </label>
                <input type="password" required value={password} minLength={8}
                  onChange={(e) => setPassword(e.target.value)}
                  className="neon w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition-all"
                  placeholder="••••••••" />
              </div>
              <button type="submit" disabled={isLoading}
                className="glow-hover w-full bg-gradient-to-r from-cyan-500 to-teal-600 text-white py-3 rounded-xl font-medium
                  hover:from-cyan-400 hover:to-teal-500 disabled:opacity-40 transition-all text-sm">
                {isLoading ? "注册中..." : "创建账号"}
              </button>
            </form>

            <p className="text-center text-sm text-slate-500 mt-8">
              已有账号？<Link href="/login" className="text-cyan-400 font-medium hover:text-cyan-300 transition-colors">去登录 →</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
