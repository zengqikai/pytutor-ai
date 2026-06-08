"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useAuthStore } from "@/stores/auth";
import { exerciseAPI } from "@/lib/api";

const diffLabels: Record<number, string> = { 1: "入门", 2: "基础", 3: "进阶", 4: "困难", 5: "挑战" };

export default function ExercisesPage() {
  const { loadUser } = useAuthStore();
  const [exercises, setExercises] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [userCode, setUserCode] = useState("");
  const [result, setResult] = useState<any>(null);
  const [difficulty, setDifficulty] = useState(2);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { loadUser(); loadExercises(); }, []);
  const loadExercises = async () => { try { setExercises(await exerciseAPI.list()); } catch {} };

  const generateExercise = async () => {
    setGenerating(true);
    try { const res = await exerciseAPI.generate({ difficulty, count: 1 }); if (res.exercises?.length) { setExercises((p) => [res.exercises[0], ...p]); setSelected(res.exercises[0]); setUserCode(""); setResult(null); } } catch (e: any) { alert(e.message); } finally { setGenerating(false); }
  };
  const submitAnswer = async () => {
    if (!selected || !userCode.trim()) return;
    setSubmitting(true);
    try { setResult(await exerciseAPI.submit(selected.id, userCode)); } catch (e: any) { alert(e.message); } finally { setSubmitting(false); }
  };

  return (
    <div className="flex h-[calc(100vh-56px)]">
      <aside className="w-80 glass border-r border-white/[0.06] flex flex-col">
        <div className="p-5 border-b border-white/[0.06]">
          <h2 className="font-bold text-lg text-white mb-4">练习中心</h2>
          <div className="flex gap-2 mb-3">
            <select value={difficulty} onChange={(e) => setDifficulty(Number(e.target.value))}
              className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-indigo-500/30">
              {Object.entries(diffLabels).map(([k, v]) => <option key={k} value={k} className="bg-[#0f0f2a]">{"★".repeat(Number(k))} {v}</option>)}
            </select>
          </div>
          <button onClick={generateExercise} disabled={generating}
            className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl text-sm font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-lg shadow-indigo-500/15">
            {generating ? "生成中..." : "✨ AI 生成练习"}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {exercises.map((ex) => (
            <button key={ex.id} onClick={() => { setSelected(ex); setUserCode(""); setResult(null); }}
              className={`w-full text-left p-4 rounded-xl transition-all border ${selected?.id === ex.id ? "border-indigo-500/30 bg-indigo-500/10" : "border-white/[0.04] hover:border-white/[0.08]"}`}>
              <p className="font-semibold text-sm text-slate-200 truncate mb-1.5">{ex.title}</p>
              <div className="flex items-center gap-2">
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-slate-400 font-medium">{diffLabels[ex.difficulty]}</span>
                {ex.concepts && <span className="text-[10px] text-slate-500 truncate">{ex.concepts}</span>}
              </div>
            </button>
          ))}
        </div>
      </aside>

      <div className="flex-1 flex flex-col">
        {selected ? (
          <>
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-3xl mx-auto p-8">
                <div className="mb-6"><h1 className="text-xl font-bold text-white mb-2">{selected.title}</h1>
                  <div className="flex items-center gap-3"><span className="text-xs px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-slate-400 font-medium">{"★".repeat(selected.difficulty)} {diffLabels[selected.difficulty]}</span><span className="text-xs text-slate-500">{selected.concepts || "通用"}</span></div>
                </div>
                <div className="glass rounded-2xl p-8 border-white/[0.06] prose-dark"><ReactMarkdown>{selected.description}</ReactMarkdown></div>
                {selected.example_input && (
                  <div className="mt-6 grid grid-cols-2 gap-4">
                    <div className="glass rounded-xl p-5 border-white/[0.06]"><p className="text-xs text-slate-500 uppercase tracking-wider mb-2">示例输入</p><pre className="text-sm text-slate-300 font-mono whitespace-pre-wrap">{selected.example_input}</pre></div>
                    <div className="glass rounded-xl p-5 border-white/[0.06]"><p className="text-xs text-slate-500 uppercase tracking-wider mb-2">示例输出</p><pre className="text-sm text-slate-300 font-mono whitespace-pre-wrap">{selected.example_output}</pre></div>
                  </div>
                )}
              </div>
            </div>
            <div className="border-t border-white/[0.06] glass p-5">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium text-slate-300">你的代码</p>
                  {result?.test_results && <span className={`text-sm font-bold ${result.test_results.passed === result.test_results.total ? "text-emerald-400" : "text-rose-400"}`}>{result.test_results.passed}/{result.test_results.total} 通过</span>}
                </div>
                <textarea value={userCode} onChange={(e) => setUserCode(e.target.value)}
                  placeholder="# Write your Python code here..."
                  className="neon w-full h-36 bg-white/[0.04] border border-white/[0.08] rounded-xl p-4 font-mono text-sm text-white placeholder-slate-600 resize-none outline-none transition-all" />
                <div className="flex justify-between items-center mt-3">
                  <button onClick={submitAnswer} disabled={submitting || !userCode.trim()}
                    className="glow-hover px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl text-sm font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40 transition-all">
                    {submitting ? "判题中..." : "提交答案"}
                  </button>
                </div>
                {result?.execution && (
                  <div className="mt-4 p-4 glass rounded-xl border border-white/[0.06]">
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">执行结果</p>
                    {result.execution.stdout && <pre className="text-emerald-400 text-sm whitespace-pre-wrap mb-2">{result.execution.stdout}</pre>}
                    {result.execution.stderr && <pre className="text-rose-400 text-sm whitespace-pre-wrap mb-2">{result.execution.stderr}</pre>}
                    <p className="text-xs text-slate-500">状态: {result.execution.status} | 耗时: {result.execution.runtime_ms}ms</p>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center animate-fade-in">
              <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-4"><span className="text-2xl">📝</span></div>
              <p className="text-slate-500">选择一个练习或让 AI 生成新题目</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
