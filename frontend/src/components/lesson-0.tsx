"use client";

import { useState } from "react";
import Editor from "@monaco-editor/react";

interface Step {
  role: "assistant" | "user_action";
  content: string;
  code?: string;
  action?: "run" | "edit" | "continue";
  actionLabel?: string;
}

const steps: Step[] = [
  { role: "assistant", content: "你好！欢迎来到 PyTutor。在开始之前，让我先告诉你：**什么是代码**。\n\n代码就像是一份**说明书**——你写下指令，计算机会按照你的指令一步步执行。Python 是最适合初学者的编程语言之一，因为它读起来很像英语。" },
  { role: "assistant", content: "现在，让我展示你的**第一行 Python 代码** 👇", code: `print("Hello, Python!")` },
  { role: "assistant", content: "`print()` 是 Python 中的一个**函数**——它的作用是把你写在括号里的内容**显示在屏幕上**。\n\n现在，点击右侧的 ▶ **运行** 按钮试试看！", action: "run", actionLabel: "我运行了" },
  { role: "assistant", content: "太棒了！你应该在下方看到了 `Hello, Python!` 这几个字。\n\n这就是**输出（Output）**——程序运行后产生的结果。`print()` 把你写的内容'打印'到了屏幕上。" },
  { role: "assistant", content: "现在试试自己动手！把双引号里的文字改成你自己的话，比如 `print(\"你好，世界！\")`，然后再运行一次。", action: "edit", actionLabel: "我改好了并运行了" },
  { role: "assistant", content: "完美！你已经完成了：\n\n1. ✅ 理解了什么是代码\n2. ✅ 运行了第一行 Python 代码\n3. ✅ 理解了 `print()` 的作用\n4. ✅ 修改了代码并看到了不同的输出\n\n你已经正式成为 Python 初学者了！🎉" },
];

export function Lesson0({ onComplete }: { onComplete: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [code, setCode] = useState(`print("Hello, Python!")`);
  const [output, setOutput] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const step = steps[stepIndex];
  const isLast = stepIndex === steps.length - 1;

  const advance = () => {
    if (isLast) {
      complete();
      return;
    }
    setStepIndex((i) => i + 1);
  };

  const runCode = async () => {
    setRunning(true);
    try {
      const token = localStorage.getItem("auth_token");
      const { codeAPI } = await import("@/lib/api");
      const res = await codeAPI.submit(code);
      const r = res.result || res;
      setOutput(r.stdout || r.stderr || "(无输出)");
    } catch {
      setOutput("运行出错，请检查代码");
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

  return (
    <div className="fixed inset-0 z-50 flex bg-[#06060f]">
      {/* Left: Chat guide */}
      <div className="flex-1 flex flex-col max-w-[600px] border-r border-white/[0.06]">
        <div className="p-4 border-b border-white/[0.06] flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold">Py</div>
          <span className="font-semibold text-white text-sm">新手教程 · Lesson 0</span>
          <span className="ml-auto text-xs text-slate-500">步骤 {stepIndex + 1}/{steps.length}</span>
        </div>
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Show previous steps */}
          {steps.slice(0, stepIndex + 1).map((s, i) => (
            <div key={i} className="space-y-2">
              {s.role === "assistant" && (
                <div className="flex gap-3 animate-fade-in">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-1">AI</div>
                  <div className="glass border-white/[0.06] rounded-xl px-4 py-3 text-sm text-slate-300 leading-relaxed flex-1">
                    <div style={{ whiteSpace: "pre-wrap" }}>{s.content}</div>
                    {s.code && (
                      <div className="mt-3 bg-[#0a0a14] rounded-lg p-3 border border-white/[0.06]">
                        <pre className="text-emerald-300 text-xs font-mono">{s.code}</pre>
                      </div>
                    )}
                    {i === stepIndex && !isLast && (
                      <button onClick={advance} className="mt-3 px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-500 transition-colors">
                        {s.actionLabel || "继续 →"}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
          {isLast && (
            <button onClick={complete} className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 text-white py-3 rounded-xl text-sm font-medium hover:from-emerald-500 hover:to-teal-500 transition-all animate-fade-in">
              🎉 完成新手教程，开始学习！
            </button>
          )}
        </div>
      </div>

      {/* Right: Code Editor */}
      <div className="flex-1 flex flex-col bg-[#0a0a14]">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
          <span className="text-sm font-medium text-slate-300">Python 编辑器</span>
          <button onClick={runCode} disabled={running} className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-colors">
            {running ? "运行中..." : "▶ 运行"}
          </button>
        </div>
        <div className="flex-1">
          <Editor height="100%" defaultLanguage="python" theme="vs-dark" value={code}
            onChange={(v) => setCode(v || "")}
            options={{ fontSize: 16, fontFamily: "var(--font-geist-mono), monospace", minimap: { enabled: false }, scrollBeyondLastLine: false, lineNumbers: "on", padding: { top: 12 }, automaticLayout: true }} />
        </div>
        <div className="border-t border-white/[0.06] p-4 min-h-[100px]">
          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">输出</p>
          {output ? (
            <pre className="text-sm text-emerald-300 font-mono whitespace-pre-wrap bg-emerald-500/5 rounded-lg p-3">{output}</pre>
          ) : (
            <p className="text-sm text-slate-600 italic">点击 ▶ 运行 查看代码输出</p>
          )}
        </div>
      </div>
    </div>
  );
}
