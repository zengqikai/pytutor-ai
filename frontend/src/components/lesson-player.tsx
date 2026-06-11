"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { API_BASE_URL } from "@/lib/api";
import type { Lesson, LessonStep } from "@/data/tutorial-data";
import { TUTORIAL_LESSONS } from "@/data/tutorial-data";

interface Props {
  startLessonId?: string;
  userId: string;
  onComplete: () => void;
}

function getStorageKey(userId: string) {
  return `pytutor_progress_${userId}`;
}

function loadProgress(userId: string, startLessonId?: string) {
  try {
    const raw = localStorage.getItem(getStorageKey(userId));
    if (raw) {
      const saved = JSON.parse(raw);
      if (typeof saved.lessonIdx === "number" && typeof saved.stepIdx === "number") {
        return saved;
      }
    }
  } catch {}
  const startIdx = TUTORIAL_LESSONS.findIndex((l) => l.id === startLessonId);
  return { lessonIdx: startIdx >= 0 ? startIdx : 0, stepIdx: 0 };
}

function saveProgress(userId: string, lessonIdx: number, stepIdx: number) {
  try {
    localStorage.setItem(getStorageKey(userId), JSON.stringify({ lessonIdx, stepIdx }));
  } catch {}
}

export function LessonPlayer({ startLessonId, userId, onComplete }: Props) {
  const [mounted, setMounted] = useState(false);
  const [lessonIdx, setLessonIdx] = useState(0);
  const [stepIdx, setStepIdx] = useState(0);
  const [code, setCode] = useState("");
  const [output, setOutput] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [misconception, setMisconception] = useState<any>(null);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [stdinInput, setStdinInput] = useState("");

  // Restore progress on mount
  useEffect(() => {
    const saved = loadProgress(userId, startLessonId);
    setLessonIdx(saved.lessonIdx);
    setStepIdx(saved.stepIdx);
    setMounted(true);
  }, []);

  const lesson = TUTORIAL_LESSONS[lessonIdx];
  const step = lesson?.steps[stepIdx];
  const isLastStep = stepIdx === (lesson?.steps.length ?? 0) - 1;
  const isLastLesson = lessonIdx === TUTORIAL_LESSONS.length - 1;

  // Save progress on step/lesson change
  useEffect(() => {
    if (mounted) saveProgress(userId, lessonIdx, stepIdx);
  }, [lessonIdx, stepIdx, mounted]);

  // Init code when lesson changes
  useEffect(() => {
    if (!mounted) return;
    setCode(lesson?.initialCode ?? "");
    setOutput(null);
    setMisconception(null);
  }, [lessonIdx, mounted]);

  const advance = () => {
    if (isLastStep) {
      completeLesson();
    } else {
      setStepIdx((i) => i + 1);
    }
  };

  const handleExit = () => {
    // Save current progress before exiting
    saveProgress(userId, lessonIdx, stepIdx);
    onComplete();
  };

  const completeLesson = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      await fetch(`${API_BASE_URL}/profile/me/lesson/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ lesson_id: lesson.id }),
      });
    } catch {}

    if (isLastLesson) {
      localStorage.removeItem(getStorageKey(userId));
      onComplete();
    } else {
      const next = lessonIdx + 1;
      setLessonIdx(next);
      setStepIdx(0);
      saveProgress(userId, next, 0);
    }
  };

  const runCode = async () => {
    setRunning(true);
    setMisconception(null);
    try {
      const { codeAPI } = await import("@/lib/api");
      const res = await codeAPI.submit(code, undefined, stdinInput);
      const r = res.result || res;
      const out = r.stdout || "";
      const err = r.stderr || "";
      setOutput(err || out || "(无输出)");

      // Diagnose misconception on error
      if (err) {
        try {
          const token = localStorage.getItem("auth_token");
          const mcRes = await fetch(`${API_BASE_URL}/misconceptions/diagnose`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ code, stderr: err }),
          });
          const mcData = await mcRes.json();
          if (mcData.has_misconception) setMisconception(mcData);
        } catch {}
      }
    } catch (e: any) {
      setOutput("运行出错: " + (e.message || "请检查代码"));
    } finally {
      setRunning(false);
    }
  };

  if (!mounted || !lesson) return null;

  const content = (
    <div className="fixed inset-0 z-[9999] flex bg-[#0a0a14] text-white" style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* Left: AI Tutor Guide */}
      <div className="w-[460px] flex-shrink-0 flex flex-col border-r border-white/[0.08] bg-[#060610]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/[0.06] flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold">Py</div>
          <div>
            <span className="font-semibold text-sm">{lesson.title}</span>
            <p className="text-[10px] text-slate-500">{lesson.desc}</p>
          </div>
          <span className="ml-auto text-xs text-slate-500">课程 {lessonIdx + 1}/{TUTORIAL_LESSONS.length}</span>
          {/* Exit button */}
          <button
            onClick={() => setShowExitConfirm(true)}
            className="ml-3 px-4 py-1.5 rounded-lg bg-white/[0.04] hover:bg-rose-500/10 border border-white/[0.08] hover:border-rose-500/30 text-slate-400 hover:text-rose-400 text-xs font-medium transition-all"
          >
            暂时退出
          </button>
        </div>

        {/* Steps */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {lesson.steps.slice(0, stepIdx + 1).map((s, i) => (
            <div key={i} className="flex gap-3">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5 ${
                i < stepIdx ? "bg-emerald-500/30 text-emerald-300" : "bg-gradient-to-br from-emerald-500 to-teal-600 text-white"
              }`}>
                {i < stepIdx ? "✓" : "AI"}
              </div>
              <div className="flex-1 glass border-white/[0.06] rounded-xl px-4 py-3 text-sm text-slate-300 leading-relaxed">
                <div style={{ whiteSpace: "pre-wrap" }} dangerouslySetInnerHTML={{ __html: s.content.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>').replace(/`([^`]+)`/g, '<code class="bg-white/10 px-1 rounded text-emerald-300">$1</code>') }} />
                {s.code && (
                  <div className="mt-2 bg-black/40 rounded-lg p-3 border border-white/[0.06]">
                    <pre className="text-emerald-300 text-sm font-mono whitespace-pre-wrap">{s.code}</pre>
                  </div>
                )}
                {i === stepIdx && !isLastStep && (
                  <button onClick={advance} className="mt-3 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors">
                    {s.actionHint || "继续 →"}
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Misconception card */}
          {misconception && (
            <div className="flex gap-3 animate-fade-in">
              <div className="w-7 h-7 rounded-lg bg-amber-500/30 flex items-center justify-center text-xs flex-shrink-0 mt-0.5">🧠</div>
              <div className="flex-1 bg-amber-500/5 border border-amber-500/20 rounded-xl px-4 py-3">
                <p className="text-xs font-semibold text-amber-400">误区诊断：{misconception.misconception_name}</p>
                <p className="text-xs text-amber-300/60 mt-1">{misconception.evidence}</p>
              </div>
            </div>
          )}

          {/* Complete button */}
          {isLastStep && (
            <button onClick={advance} className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white py-3 rounded-xl text-sm font-medium transition-all">
              {isLastLesson ? "🎉 完成全部教程！" : `下一课：${TUTORIAL_LESSONS[lessonIdx + 1]?.title ?? ""} →`}
            </button>
          )}
        </div>

        {/* Progress bar */}
        <div className="px-5 py-3 border-t border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-500">步骤 {stepIdx + 1}/{lesson.steps.length}</span>
            <div className="flex-1 h-1 bg-white/[0.06] rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all" style={{ width: `${((stepIdx + 1) / lesson.steps.length) * 100}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Right: Code Lab */}
      <div className="flex-1 flex flex-col">
        <div className="px-5 py-3 border-b border-white/[0.06] flex items-center justify-between bg-[#060610]">
          <span className="text-sm font-medium text-slate-300">Python 编辑器</span>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">点击运行 →</span>
            <button onClick={runCode} disabled={running}
              className="px-7 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-emerald-500/30"
            >
              {running ? "⏳ 运行中..." : "▶ 运 行"}
            </button>
          </div>
        </div>
        {/* Code Editor — top half */}
        <div className="flex-[2] p-4 bg-[#0a0a14] min-h-0">
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full h-full bg-black/60 border border-white/[0.08] rounded-xl p-4 text-emerald-300 font-mono text-base resize-none outline-none focus:border-emerald-500/40 leading-relaxed"
            spellCheck={false}
          />
        </div>
        {/* Stdin Input */}
        <div className="border-t border-white/[0.06] px-4 py-2 bg-[#060610]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex-shrink-0">输入 (stdin)</span>
            <input
              value={stdinInput}
              onChange={(e) => setStdinInput(e.target.value)}
              placeholder="如果代码用 input()，在这里输入数据..."
              className="flex-1 bg-black/40 border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-green-300 font-mono outline-none focus:border-emerald-500/30 placeholder:text-slate-600"
            />
          </div>
        </div>
        {/* Output — bottom, bigger */}
        <div className="flex-1 border-t border-white/[0.06] bg-[#060610] min-h-0 overflow-y-auto">
          <div className="px-4 py-2 border-b border-white/[0.04]">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">输出</p>
          </div>
          <div className="p-4">
            {output ? (
              <pre className={`text-sm font-mono whitespace-pre-wrap ${output.includes("Error") || output.includes("Traceback") ? "text-rose-400" : "text-emerald-300"}`}>{output}</pre>
            ) : (
              <p className="text-sm text-slate-600 italic">点击 ▶ 运行 查看代码输出</p>
            )}
          </div>
        </div>
      </div>

      {/* Exit confirmation modal */}
      {showExitConfirm && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="glass rounded-2xl border border-white/[0.08] p-8 max-w-md w-full mx-4 text-center">
            <span className="text-4xl">📝</span>
            <h3 className="text-lg font-bold text-white mt-3">进度已自动保存</h3>
            <p className="text-sm text-slate-400 mt-2 leading-relaxed">
              你目前学到<strong className="text-emerald-400"> {lesson.title} </strong>（第 {stepIdx + 1}/{lesson.steps.length} 步）。
            </p>
            <p className="text-sm text-slate-500 mt-2 leading-relaxed">
              下次点击右下角的 <span className="text-indigo-400">🎓 按钮</span>，<br/>就可以从当前位置继续学习。
            </p>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowExitConfirm(false)}
                className="flex-1 px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-slate-300 text-sm font-medium hover:bg-white/[0.08] transition-colors">
                继续学习
              </button>
              <button onClick={handleExit}
                className="flex-1 px-4 py-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm font-medium hover:bg-rose-500/20 transition-colors">
                确认退出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return createPortal(content, document.body);
}
