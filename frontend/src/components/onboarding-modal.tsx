"use client";

import { useState } from "react";

const options = [
  { key: "A", label: "我完全没有编程基础", desc: "从零开始，一步步引导你写第一行代码", icon: "🌱" },
  { key: "B", label: "我学过一点 Python", desc: "巩固基础，学习常见误区和调试技巧", icon: "📗" },
  { key: "C", label: "我会基础语法，想练习和调试", desc: "进入练习中心，挑战 ACM 模式题目", icon: "💻" },
  { key: "D", label: "我只想自由提问", desc: "直接进入 AI Tutor 对话", icon: "💬" },
];

export function OnboardingModal({ onComplete }: { onComplete: (level: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!selected) return;
    setSubmitting(true);
    try {
      const token = localStorage.getItem("auth_token");
      await fetch("http://localhost:8000/api/v1/profile/me/onboarding", {
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
          {submitting ? "设置中..." : selected === "A" ? "开始新手教程" : "进入 PyTutor"}
        </button>
      </div>
    </div>
  );
}
