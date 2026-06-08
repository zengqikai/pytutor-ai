"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useAuthStore } from "@/stores/auth";
import { exerciseAPI } from "@/lib/api";

const diffLabels: Record<number, string> = { 1: "入门", 2: "基础", 3: "进阶", 4: "困难", 5: "挑战" };
const diffColors: Record<number, string> = {
  1: "bg-emerald-100 text-emerald-700", 2: "bg-blue-100 text-blue-700",
  3: "bg-amber-100 text-amber-700", 4: "bg-orange-100 text-orange-700", 5: "bg-rose-100 text-rose-700"
};

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
    try {
      const res = await exerciseAPI.generate({ difficulty, count: 1 });
      if (res.exercises?.length) {
        setExercises((p) => [res.exercises[0], ...p]);
        setSelected(res.exercises[0]); setUserCode(""); setResult(null);
      }
    } catch (e: any) { alert(e.message); }
    finally { setGenerating(false); }
  };

  const submitAnswer = async () => {
    if (!selected || !userCode.trim()) return;
    setSubmitting(true);
    try { const res = await exerciseAPI.submit(selected.id, userCode); setResult(res); } catch (e: any) { alert(e.message); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* 左侧题目列表 */}
      <aside className="w-80 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-5 border-b border-slate-100">
          <h2 className="font-bold text-lg text-slate-800 mb-4">练习中心</h2>
          <div className="flex gap-2 mb-3">
            <select value={difficulty} onChange={(e) => setDifficulty(Number(e.target.value))}
              className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-300">
              {Object.entries(diffLabels).map(([k, v]) => (
                <option key={k} value={k}>{"★".repeat(Number(k))} {v}</option>
              ))}
            </select>
          </div>
          <button onClick={generateExercise} disabled={generating}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl text-sm font-medium
              hover:from-indigo-700 hover:to-violet-700 disabled:opacity-50 transition-all shadow-sm shadow-indigo-200">
            {generating ? "AI 生成中..." : "✨ AI 生成练习"}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {exercises.map((ex) => (
            <button key={ex.id} onClick={() => { setSelected(ex); setUserCode(""); setResult(null); }}
              className={`w-full text-left p-4 rounded-xl transition-all border
                ${selected?.id === ex.id
                  ? "border-indigo-200 bg-indigo-50/50 shadow-sm"
                  : "border-slate-100 hover:border-slate-200 hover:shadow-sm"}`}>
              <p className="font-semibold text-sm text-slate-800 truncate mb-1.5">{ex.title}</p>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${diffColors[ex.difficulty] || ""}`}>
                  {diffLabels[ex.difficulty]}
                </span>
                {ex.concepts && <span className="text-[10px] text-slate-400 truncate">{ex.concepts}</span>}
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* 右侧题目详情 + 作答 */}
      <div className="flex-1 flex flex-col">
        {selected ? (
          <>
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-3xl mx-auto p-8">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h1 className="text-xl font-bold text-slate-800 mb-2">{selected.title}</h1>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${diffColors[selected.difficulty] || ""}`}>
                        {"★".repeat(selected.difficulty)} {diffLabels[selected.difficulty]}
                      </span>
                      <span className="text-xs text-slate-400">{selected.concepts || "通用"}</span>
                    </div>
                  </div>
                </div>

                <div className="prose-custom bg-white rounded-2xl p-8 border border-slate-200/60 shadow-sm">
                  <ReactMarkdown>{selected.description}</ReactMarkdown>
                </div>

                {selected.example_input && (
                  <div className="mt-6 grid grid-cols-2 gap-4">
                    <div className="bg-slate-50 rounded-xl p-5 border border-slate-200/60">
                      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">示例输入</p>
                      <pre className="text-sm text-slate-700 font-mono whitespace-pre-wrap">{selected.example_input}</pre>
                    </div>
                    <div className="bg-slate-50 rounded-xl p-5 border border-slate-200/60">
                      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">示例输出</p>
                      <pre className="text-sm text-slate-700 font-mono whitespace-pre-wrap">{selected.example_output}</pre>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 作答区 */}
            <div className="border-t border-slate-200/60 bg-white p-5">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium text-slate-600">你的代码</p>
                  {result?.test_results && (
                    <span className={`text-sm font-bold flex items-center gap-1.5
                      ${result.test_results.passed === result.test_results.total ? "text-emerald-600" : "text-rose-600"}`}>
                      {result.test_results.passed === result.test_results.total ? "✅" : "❌"}
                      {result.test_results.passed}/{result.test_results.total} 通过
                    </span>
                  )}
                </div>
                <textarea value={userCode} onChange={(e) => setUserCode(e.target.value)}
                  placeholder="# 在这里写你的 Python 代码..."
                  className="w-full h-36 border border-slate-200 rounded-xl p-4 font-mono text-sm resize-none outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 transition-all bg-slate-50" />
                <div className="flex justify-between items-center mt-3">
                  <button onClick={submitAnswer} disabled={submitting || !userCode.trim()}
                    className="px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl text-sm font-medium
                      hover:from-indigo-700 hover:to-violet-700 disabled:opacity-40 transition-all shadow-sm shadow-indigo-200">
                    {submitting ? "判题中..." : "提交答案"}
                  </button>
                </div>
                {result?.execution && (
                  <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">执行结果</p>
                    {result.execution.stdout && <pre className="text-emerald-600 text-sm whitespace-pre-wrap mb-2">{result.execution.stdout}</pre>}
                    {result.execution.stderr && <pre className="text-rose-600 text-sm whitespace-pre-wrap mb-2">{result.execution.stderr}</pre>}
                    <p className="text-xs text-slate-400">状态: {result.execution.status} | 耗时: {result.execution.runtime_ms}ms</p>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center animate-fade-in">
              <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">📝</span>
              </div>
              <p className="text-slate-500">选择一个练习或让 AI 生成新题目</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
