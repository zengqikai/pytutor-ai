"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

interface Step {
  role: "assistant";
  content: string;
  code?: string;
  actionLabel?: string;
}

const steps: Step[] = [
  { role: "assistant", content: "你好！欢迎来到 PyTutor。在开始之前，让我先告诉你：**什么是代码**。\n\n代码就像是一份**说明书**——你写下指令，计算机会按照你的指令一步步执行。Python 是最适合初学者的编程语言之一，因为它读起来很像英语。" },
  { role: "assistant", content: "现在，让我展示你的**第一行 Python 代码** 👇\n\n请点击右侧绿色的 **▶ 运行** 按钮试试看！", code: `print("Hello, Python!")` },
  { role: "assistant", content: "太棒了！你应该在下方看到了 `Hello, Python!`\n\n这就是**输出（Output）**——程序运行后产生的结果。`print()` 把你写的内容显示到了屏幕上。" },
  { role: "assistant", content: "现在试试自己动手！把双引号里的文字改成你自己的话，比如 `print(\"你好，世界！\")`，然后再运行一次。", actionLabel: "我改好了并运行了" },
  { role: "assistant", content: "完美！你已经完成了：\n\n1. ✅ 理解了什么是代码\n2. ✅ 运行了第一行 Python 代码\n3. ✅ 理解了 `print()` 的作用\n4. ✅ 修改代码并看到不同的输出\n\n你已经正式成为 Python 初学者了！🎉" },
];

export function Lesson0({ onComplete }: { onComplete: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [code, setCode] = useState(`print("Hello, Python!")`);
  const [output, setOutput] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const step = steps[stepIndex];
  const isLast = stepIndex === steps.length - 1;

  const advance = () => {
    if (isLast) { complete(); return; }
    setStepIndex((i) => i + 1);
  };

  const runCode = async () => {
    setRunning(true);
    try {
      const { codeAPI } = await import("@/lib/api");
      const res = await codeAPI.submit(code);
      const r = res.result || res;
      setOutput(r.stdout || r.stderr || "(无输出)");
    } catch (e: any) {
      setOutput("运行出错: " + (e.message || "请检查代码"));
    } finally {
      setRunning(false);
    }
  };

  const complete = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      await fetch("http://localhost:8000/api/v1/profile/me/lesson/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ lesson_id: "lesson_0" }),
      });
    } catch {}
    onComplete();
  };

  if (!mounted) return null;

  const content = (
    <div className="fixed inset-0 z-[9999] flex bg-[#0a0a14] text-white" style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* Left: Guide */}
      <div className="w-[480px] flex-shrink-0 flex flex-col border-r border-white/[0.08] bg-[#060610]">
        <div className="px-5 py-4 border-b border-white/[0.06] flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold">Py</div>
          <span className="font-semibold text-sm">新手教程 · Lesson 0</span>
          <span className="ml-auto text-xs text-slate-500">{stepIndex + 1}/{steps.length}</span>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {steps.slice(0, stepIndex + 1).map((s, i) => (
            <div key={i} className="flex gap-3">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 mt-0.5">AI</div>
              <div className="flex-1 glass border-white/[0.06] rounded-xl px-4 py-3 text-sm text-slate-300 leading-relaxed">
                <div style={{ whiteSpace: "pre-wrap" }}>{s.content}</div>
                {s.code && (
                  <div className="mt-2 bg-black/40 rounded-lg p-3 border border-white/[0.06]">
                    <pre className="text-emerald-300 text-sm font-mono">{s.code}</pre>
                  </div>
                )}
                {i === stepIndex && !isLast && (
                  <button onClick={advance} className="mt-3 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors">
                    {s.actionLabel || "继续 →"}
                  </button>
                )}
              </div>
            </div>
          ))}
          {isLast && (
            <button onClick={complete} className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white py-3 rounded-xl text-sm font-medium transition-all">
              🎉 完成新手教程，开始学习！
            </button>
          )}
        </div>
      </div>

      {/* Right: Code Editor */}
      <div className="flex-1 flex flex-col">
        <div className="px-5 py-3 border-b border-white/[0.06] flex items-center justify-between bg-[#060610]">
          <span className="text-sm font-medium text-slate-300">Python 编辑器</span>
          <button
            onClick={runCode}
            disabled={running}
            className="px-8 py-3 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-base font-bold transition-all shadow-lg shadow-emerald-500/30"
            style={{ cursor: running ? "not-allowed" : "pointer" }}
          >
            {running ? "⏳ 运行中..." : "▶ 运 行"}
          </button>
        </div>
        <div className="flex-1 p-4 bg-[#0a0a14]">
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full h-full bg-black/60 border border-white/[0.08] rounded-xl p-4 text-emerald-300 font-mono text-lg resize-none outline-none focus:border-emerald-500/40"
            spellCheck={false}
          />
        </div>
        <div className="border-t border-white/[0.06] p-4 bg-[#060610] min-h-[120px]">
          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">输出</p>
          {output ? (
            <pre className="text-sm text-emerald-300 font-mono whitespace-pre-wrap">{output}</pre>
          ) : (
            <p className="text-sm text-slate-600 italic">点击 ▶ 运行 查看代码输出</p>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
