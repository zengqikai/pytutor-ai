"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { API_BASE_URL } from "@/lib/api";
import { DIAGNOSTIC_TASKS } from "@/data/diagnostic-tasks";

export function DiagnosticFlow({ onComplete }: { onComplete: (result: any) => void }) {
  const [step, setStep] = useState<"intro" | number | "result">("intro");
  const [answers, setAnswers] = useState<Record<number, string>>({});

  const currentTask = typeof step === "number" ? DIAGNOSTIC_TASKS[step] : null;
  const totalTasks = DIAGNOSTIC_TASKS.length;

  const handleAnswer = (key: string) => {
    if (typeof step !== "number") return;
    setAnswers((prev) => ({ ...prev, [currentTask!.id]: key }));
  };

  const goNext = () => {
    if (typeof step !== "number") return;
    if (step + 1 < totalTasks) {
      setStep(step + 1);
    } else {
      setStep("result");
    }
  };

  const computeResult = () => {
    let correct = 0;
    const weakConcepts: string[] = [];
    const misconceptions: string[] = [];
    const masteredConcepts: string[] = [];

    for (const task of DIAGNOSTIC_TASKS) {
      const userAnswer = answers[task.id];
      const correctOption = task.options.find((o) => o.isCorrect);
      if (userAnswer === correctOption?.key) {
        correct++;
        masteredConcepts.push(...task.relatedConcepts);
      } else {
        weakConcepts.push(...task.relatedConcepts);
        if (task.misconception) misconceptions.push(task.misconception);
      }
    }

    return {
      total: totalTasks,
      correct,
      mastered: [...new Set(masteredConcepts)],
      weak: [...new Set(weakConcepts)],
      misconceptions: [...new Set(misconceptions)],
      level: correct === totalTasks ? "solid" : correct >= totalTasks - 2 ? "medium" : "beginner",
    };
  };

  const handleFinish = () => {
    const result = computeResult();
    // Save to profile
    try {
      const token = localStorage.getItem("auth_token");
      fetch(`${API_BASE_URL}/profile/me/onboarding`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ skill_level: "B", diagnosis: result }),
      });
    } catch {}
    onComplete(result);
  };

  // Intro page
  if (step === "intro") {
    const content = (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#0a0a14]" style={{ fontFamily: "system-ui, sans-serif" }}>
        <div className="max-w-lg w-full mx-4 text-center">
          <span className="text-5xl">📋</span>
          <h2 className="text-2xl font-bold text-white mt-4">基础诊断</h2>
          <p className="text-sm text-slate-400 mt-3 leading-relaxed">
            你已经学过一点 Python，接下来 PyTutor 会通过 <strong className="text-white">{totalTasks} 个简单任务</strong> 了解你的基础情况。
          </p>
          <p className="text-sm text-slate-500 mt-2 leading-relaxed">
            这些任务<strong className="text-emerald-400">不是考试</strong>，答错也没有关系。<br/>
            系统会根据你的表现判断你已经掌握的内容和需要复习的知识点，<br/>
            然后为你推荐适合的学习路径。
          </p>
          <div className="flex gap-3 mt-8 justify-center">
            <button onClick={() => onComplete({ skipped: true })} className="px-5 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-slate-400 text-sm hover:text-white transition-colors">
              跳过诊断，直接学习
            </button>
            <button onClick={() => setStep(0)} className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium hover:from-indigo-500 transition-all">
              开始基础诊断 →
            </button>
          </div>
        </div>
      </div>
    );
    return createPortal(content, document.body);
  }

  // Result page
  if (step === "result") {
    const result = computeResult();
    const pct = Math.round((result.correct / result.total) * 100);
    const content = (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#0a0a14] overflow-y-auto" style={{ fontFamily: "system-ui, sans-serif" }}>
        <div className="max-w-lg w-full mx-4 py-8">
          <div className="text-center mb-6">
            <span className="text-5xl">{pct >= 80 ? "🎉" : pct >= 50 ? "📗" : "🌱"}</span>
            <h2 className="text-2xl font-bold text-white mt-3">诊断报告</h2>
            <p className="text-slate-400 text-sm mt-1">正确 {result.correct}/{result.total}（{pct}%）</p>
          </div>

          {/* Mastered */}
          <div className="glass rounded-xl border border-white/[0.06] p-4 mb-3">
            <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2">✅ 已掌握</p>
            <div className="flex flex-wrap gap-1.5">
              {result.mastered.map((c) => (
                <span key={c} className="text-[10px] bg-emerald-500/10 text-emerald-300 px-2 py-0.5 rounded-full">{c}</span>
              ))}
              {result.mastered.length === 0 && <span className="text-xs text-slate-500">暂未检测到</span>}
            </div>
          </div>

          {/* Weak */}
          <div className="glass rounded-xl border border-white/[0.06] p-4 mb-3">
            <p className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2">⚠️ 需要加强</p>
            <div className="flex flex-wrap gap-1.5">
              {result.weak.map((c) => (
                <span key={c} className="text-[10px] bg-amber-500/10 text-amber-300 px-2 py-0.5 rounded-full">{c}</span>
              ))}
              {result.weak.length === 0 && <span className="text-xs text-emerald-400">没有薄弱点！</span>}
            </div>
          </div>

          {/* Misconceptions */}
          {result.misconceptions.length > 0 && (
            <div className="glass rounded-xl border border-white/[0.06] p-4 mb-3">
              <p className="text-xs font-semibold text-rose-400 uppercase tracking-wider mb-2">🧠 可能误区</p>
              <div className="flex flex-wrap gap-1.5">
                {result.misconceptions.map((m) => (
                  <span key={m} className="text-[10px] bg-rose-500/10 text-rose-300 px-2 py-0.5 rounded-full">{m}</span>
                ))}
              </div>
            </div>
          )}

          {/* Recommendation */}
          <div className="glass rounded-xl border border-white/[0.08] p-4 bg-gradient-to-r from-indigo-500/5 to-violet-500/5">
            <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">📖 推荐下一步</p>
            <p className="text-sm text-slate-300 leading-relaxed">
              {result.level === "solid"
                ? "你的基础很扎实！可以直接进入练习中心，挑战更难的题目。"
                : result.level === "medium"
                ? "基础不错，但个别知识点还需要巩固。建议针对性复习上面标注的薄弱项。"
                : "建议从新手教程 Lesson 1（print 和变量）开始，系统性地巩固基础。"}
            </p>
          </div>

          <div className="flex gap-3 mt-6">
            {result.level !== "solid" && (
              <button onClick={handleFinish} className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium hover:from-indigo-500 transition-all">
                进入补漏课程 →
              </button>
            )}
            <button onClick={handleFinish} className={`${result.level !== "solid" ? "" : "flex-1"} px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] text-slate-300 text-sm font-medium hover:bg-white/[0.08] transition-colors`}>
              {result.level === "solid" ? "进入练习中心 →" : "跳过，直接学习"}
            </button>
          </div>
        </div>
      </div>
    );
    return createPortal(content, document.body);
  }

  // Question page
  const task = currentTask;
  if (!task) return null;

  const content = (
    <div className="fixed inset-0 z-[9999] flex bg-[#0a0a14]" style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* Left: question */}
      <div className="flex-1 flex flex-col justify-center px-10 max-w-[550px]">
        <div className="text-xs text-slate-500 mb-2">第 {task.id}/{totalTasks} 题 · {task.topic}</div>
        <div className="bg-black/40 border border-white/[0.06] rounded-xl p-5 mb-4">
          <pre className="text-emerald-300 text-base font-mono whitespace-pre-wrap">{task.code}</pre>
        </div>
        <p className="text-white text-lg font-medium mb-6">{task.question}</p>
        <div className="space-y-2">
          {task.options.map((opt) => {
            const isSelected = answers[task.id] === opt.key;
            return (
              <button
                key={opt.key}
                onClick={() => handleAnswer(opt.key)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  isSelected
                    ? "border-indigo-500/40 bg-indigo-500/10 text-white"
                    : "border-white/[0.06] hover:border-white/[0.12] bg-white/[0.02] text-slate-300"
                }`}
              >
                <span className="inline-block w-6 h-6 rounded-full bg-white/[0.06] text-center text-xs leading-6 mr-3">{opt.key}</span>
                {opt.text}
              </button>
            );
          })}
        </div>
        <button
          onClick={goNext}
          disabled={!answers[task.id]}
          className="mt-6 px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 text-white text-sm font-medium transition-all"
        >
          {task.id === totalTasks ? "查看诊断报告 →" : "下一题 →"}
        </button>
      </div>

      {/* Right: code runner */}
      <div className="flex-1 flex flex-col bg-[#060610] border-l border-white/[0.06]">
        <div className="px-5 py-3 border-b border-white/[0.06]">
          <span className="text-sm font-medium text-slate-300">试试运行代码</span>
        </div>
        <div className="flex-1 p-4">
          <textarea
            value={task.code}
            readOnly
            className="w-full h-full bg-black/60 border border-white/[0.08] rounded-xl p-4 text-emerald-300 font-mono text-base resize-none outline-none leading-relaxed"
          />
        </div>
        <RunButton code={task.code} />
      </div>
    </div>
  );

  return createPortal(content, document.body);
}

function RunButton({ code }: { code: string }) {
  const [output, setOutput] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const runCode = async () => {
    setRunning(true);
    try {
      const { codeAPI } = await import("@/lib/api");
      const res = await codeAPI.submit(code);
      const r = res.result || res;
      setOutput(r.stdout || r.stderr || "(无输出)");
    } catch {
      setOutput("运行出错");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="border-t border-white/[0.06]">
      <div className="px-4 py-2 flex items-center justify-between">
        <button onClick={runCode} disabled={running}
          className="px-5 py-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white rounded-lg text-sm font-medium transition-all">
          {running ? "⏳" : "▶ 运行"}
        </button>
        <span className="text-xs text-slate-500">运行代码验证你的答案</span>
      </div>
      {output && (
        <div className="px-4 py-3 border-t border-white/[0.04]">
          <pre className={`text-sm font-mono ${output.includes("Error") ? "text-rose-400" : "text-emerald-300"}`}>{output}</pre>
        </div>
      )}
    </div>
  );
}
