"use client";

import { useState } from "react";
import { API_BASE_URL } from "@/lib/api";

const options = [
  { key: "A", label: "我完全没有编程基础", desc: "从零开始，从认识编辑器到for循环，一步步引导", icon: "🌱", btn: "开始新手教程" },
  { key: "B", label: "我学过一点 Python", desc: "跳过编辑器介绍，从 print 和变量开始学起", icon: "📗", btn: "进入基础课程" },
  { key: "C", label: "我会基础语法，想练习和调试", desc: "直接进入练习中心，挑战 ACM 模式题目", icon: "💻", btn: "进入练习中心" },
  { key: "D", label: "我只想自由提问", desc: "直接进入 AI Tutor，想问什么问什么", icon: "💬", btn: "开始对话" },
];

export function OnboardingModal({ onComplete }: { onComplete: (level: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!selected) return;
    setSubmitting(true);
    try {
      const token = localStorage.getItem("auth_token");
      await fetch(`${API_BASE_URL}/profile/me/onboarding`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ skill_level: selected }),
      });
    } catch {}
    onComplete(selected);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass rounded-2xl border border-white/[0.08] p-8 max-w-lg w-full mx-4 animate-fade-in shadow-2xl">
        <div className="text-center mb-6">
          <span className="text-4xl">🐍</span>
          <h2 className="text-xl font-bold text-white mt-3">欢迎来到 PyTutor</h2>
          <p className="text-sm text-slate-400 mt-1">请选择你的 Python 基础，我会为你定制学习路径</p>
        </div>

        <div className="space-y-2 mb-6">
          {options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => setSelected(opt.key)}
              className={`w-full text-left p-4 rounded-xl border transition-all ${
                selected === opt.key
                  ? "border-indigo-500/40 bg-indigo-500/10"
                  : "border-white/[0.06] hover:border-white/[0.12] bg-white/[0.02]"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">{opt.icon}</span>
                <div>
                  <p className="text-sm font-medium text-slate-200">{opt.label}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{opt.desc}</p>
                </div>
                {selected === opt.key && (
                  <span className="ml-auto w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="4"><polyline points="20 6 9 17 4 12"/></svg>
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>

        <button
          onClick={handleSubmit}
          disabled={!selected || submitting}
          className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-3 rounded-xl text-sm font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-30 transition-all"
        >
          {submitting ? "设置中..." : options.find(o => o.key === selected)?.btn || "进入 PyTutor"}
        </button>
      </div>
    </div>
  );
}
