"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import Editor from "@monaco-editor/react";
import { useAuthStore } from "@/stores/auth";
import { exerciseAPI } from "@/lib/api";

const diffLabels: Record<number, string> = { 1: "入门", 2: "基础", 3: "进阶", 4: "困难", 5: "挑战" };

export default function ExercisesPage() {
  const { loadUser } = useAuthStore();
  const [exercises, setExercises] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [userCode, setUserCode] = useState("# 在此编写你的代码\n");
  const [result, setResult] = useState<any>(null);
  const [difficulty, setDifficulty] = useState(2);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [customInput, setCustomInput] = useState("");
  const [testRunning, setTestRunning] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);

  useEffect(() => { loadUser(); loadExercises(); }, []);
  const loadExercises = async () => { try { setExercises(await exerciseAPI.list()); } catch {} };

  const generateExercise = async () => {
    setGenerating(true);
    try { const res = await exerciseAPI.generate({ difficulty, count: 1 }); if (res.exercises?.length) { setExercises((p) => [res.exercises[0], ...p]); setSelected(res.exercises[0]); setUserCode("# 在此编写你的代码\n"); setResult(null); setCustomInput(""); setTestResult(null); } } catch (e: any) { alert(e.message); } finally { setGenerating(false); }
  };
  const submitAnswer = async () => {
    if (!selected || !userCode.trim()) return;
    setSubmitting(true); setResult(null);
    try { const r = await exerciseAPI.submit(selected.id, userCode); setResult(r); } catch (e: any) { alert(e.message); } finally { setSubmitting(false); }
  };
  // 自测：用自定义输入运行代码
  const runTest = async () => {
    if (!userCode.trim()) return;
    setTestRunning(true); setTestResult(null);
    try {
      const { codeAPI } = await import("@/lib/api");
      const res = await codeAPI.submit(userCode, undefined, customInput);
      const exec = res.result || res;
      setTestResult({ stdout: exec.stdout || "(无输出)", stderr: exec.stderr || "", status: exec.status, runtime_ms: exec.runtime_ms });
    } catch (e: any) { setTestResult({ stderr: String(e.message) }); }
    finally { setTestRunning(false); }
  };

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* 左侧题目列表 */}
      <aside className="w-72 glass border-r border-white/[0.06] flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-white/[0.06]">
          <h2 className="font-bold text-base text-white mb-3">题库</h2>
          <div className="flex gap-2 mb-3">
            <select value={difficulty} onChange={(e) => setDifficulty(Number(e.target.value))}
              className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-indigo-500/30">
              {Object.entries(diffLabels).map(([k, v]) => <option key={k} value={k} className="bg-[#0f0f2a]">{"★".repeat(Number(k))} {v}</option>)}
            </select>
          </div>
          <button onClick={generateExercise} disabled={generating}
            className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl text-sm font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all">
            {generating ? "生成中..." : "✨ AI 生成题目"}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {exercises.map((ex) => (
            <button key={ex.id} onClick={() => { setSelected(ex); setUserCode("# 在此编写你的代码\n"); setResult(null); setCustomInput(""); setTestResult(null); }}
              className={`w-full text-left p-3 rounded-xl transition-all border ${selected?.id === ex.id ? "border-indigo-500/30 bg-indigo-500/10" : "border-white/[0.04] hover:border-white/[0.08]"}`}>
              <p className="font-semibold text-sm text-slate-200 truncate mb-1">{ex.title}</p>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-slate-400 font-medium">{diffLabels[ex.difficulty]}</span>
            </button>
          ))}
        </div>
      </aside>

      {/* 右侧：题目 + 代码 + 结果（ACM 布局） */}
      {selected ? (
        <div className="flex-1 flex">
          {/* 题目描述 */}
          <div className="flex-1 overflow-y-auto border-r border-white/[0.06]">
            <div className="max-w-2xl mx-auto p-6">
              <div className="mb-6">
                <h1 className="text-xl font-bold text-white mb-2">{selected.title}</h1>
                <div className="flex items-center gap-3">
                  <span className="text-xs px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-slate-400">
                    {"★".repeat(selected.difficulty)} {diffLabels[selected.difficulty]}
                  </span>
                  <span className="text-xs text-slate-500">{selected.concepts || "通用"}</span>
                </div>
              </div>

              <div className="glass rounded-2xl p-6 border-white/[0.06] prose-dark mb-6">
                <ReactMarkdown>{selected.description}</ReactMarkdown>
              </div>

              {selected.example_input && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="glass rounded-xl p-5 border-white/[0.06]">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">样例输入 Sample Input</p>
                    <pre className="text-sm text-emerald-300 font-mono whitespace-pre-wrap bg-emerald-500/5 rounded-lg p-3">{selected.example_input}</pre>
                  </div>
                  <div className="glass rounded-xl p-5 border-white/[0.06]">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">样例输出 Sample Output</p>
                    <pre className="text-sm text-emerald-300 font-mono whitespace-pre-wrap bg-emerald-500/5 rounded-lg p-3">{selected.example_output}</pre>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 代码编辑器 + 提交 */}
          <div className="w-[500px] flex flex-col flex-shrink-0">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
              <span className="text-sm font-medium text-slate-300">代码编辑器</span>
              <div className="flex gap-2">
                <button onClick={runTest} disabled={testRunning}
                  className="px-3 py-1.5 bg-slate-700 text-white rounded-lg text-xs font-medium hover:bg-slate-600 disabled:opacity-40 transition-all">
                  {testRunning ? "运行中..." : "▶ 运行测试"}
                </button>
                <button onClick={submitAnswer} disabled={submitting}
                  className="glow-hover px-4 py-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg text-xs font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40 transition-all">
                  {submitting ? "判题中..." : "提交判题"}
                </button>
              </div>
            </div>
            <div style={{ height: "300px" }}>
              <Editor height="100%" defaultLanguage="python" theme="vs-dark" value={userCode}
                onChange={(v) => setUserCode(v || "")}
                options={{ fontSize: 14, fontFamily: "var(--font-geist-mono), monospace", minimap: { enabled: false }, scrollBeyondLastLine: false, lineNumbers: "on", padding: { top: 8 }, automaticLayout: true }} />
            </div>

            {/* 自定义输入 + 自测结果 */}
            <div className="border-t border-white/[0.06]">
              <div className="px-4 py-2 border-b border-white/[0.04]">
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">自定义输入（模拟 stdin）</p>
              </div>
              <textarea value={customInput} onChange={(e) => setCustomInput(e.target.value)}
                placeholder="在这里输入测试数据，模拟 input() 读取的内容..."
                className="w-full bg-[#0a0a14] border-0 text-green-300 text-xs font-mono p-3 resize-none outline-none h-16" />
              {testResult && (
                <div className="border-t border-white/[0.04]">
                  <div className="px-4 py-2 border-b border-white/[0.04] flex items-center justify-between">
                    <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">自测输出</p>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${testResult.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>{testResult.status}</span>
                  </div>
                  <div className="p-3 space-y-2">
                    {testResult.stdout && <div><p className="text-[10px] text-slate-600 mb-1">stdout</p><pre className="text-emerald-400 text-xs whitespace-pre-wrap font-mono">{testResult.stdout}</pre></div>}
                    {testResult.stderr && <div><p className="text-[10px] text-slate-600 mb-1">stderr</p><pre className="text-rose-400 text-xs whitespace-pre-wrap font-mono">{testResult.stderr}</pre></div>}
                    {testResult.runtime_ms && <p className="text-[10px] text-slate-600">耗时: {testResult.runtime_ms}ms</p>}
                  </div>
                </div>
              )}
            </div>

            {/* 判题结果 */}
            <div className="border-t border-white/[0.06] bg-[#060610] max-h-[40%] overflow-y-auto">
              <div className="px-4 py-2 border-b border-white/[0.04]">
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">判题结果</p>
              </div>
              <div className="p-4">
                {result ? (
                  <div className="space-y-4">
                    {/* 总体结果 */}
                    <div className={`flex items-center gap-3 p-4 rounded-xl ${result.test_results?.passed === result.test_results?.total ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-rose-500/10 border border-rose-500/20"}`}>
                      <span className="text-2xl">{result.test_results?.passed === result.test_results?.total ? "✅" : "❌"}</span>
                      <div>
                        <p className={`font-bold ${result.test_results?.passed === result.test_results?.total ? "text-emerald-400" : "text-rose-400"}`}>
                          {result.test_results?.passed === result.test_results?.total ? "Accepted" : "Wrong Answer"}
                        </p>
                        <p className="text-sm text-slate-400">{result.test_results?.passed}/{result.test_results?.total} 测试用例通过</p>
                      </div>
                    </div>

                    {/* 每个测试用例 */}
                    {result.test_results?.details?.map((tc: any, i: number) => (
                      <div key={i} className={`p-3 rounded-lg border ${tc.passed ? "bg-emerald-500/5 border-emerald-500/10" : "bg-rose-500/5 border-rose-500/10"}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={tc.passed ? "text-emerald-400" : "text-rose-400"}>{tc.passed ? "✓" : "✗"}</span>
                          <span className="text-sm font-medium text-slate-300">{tc.description || `测试用例 ${i + 1}`}</span>
                          {tc.is_hidden && <span className="text-[10px] text-slate-600 bg-white/[0.04] px-1.5 py-0.5 rounded">隐藏</span>}
                        </div>
                        {!tc.passed && !tc.is_hidden && (
                          <div className="mt-2 space-y-1 text-xs">
                            <div><span className="text-slate-500">期望：</span><code className="text-emerald-400">{tc.expected}</code></div>
                            <div><span className="text-slate-500">实际：</span><code className="text-rose-400">{tc.got}</code></div>
                          </div>
                        )}
                      </div>
                    ))}

                    {/* 执行信息 */}
                    {result.execution && (
                      <div className="text-xs text-slate-600 space-y-0.5">
                        <p>状态: {result.execution.status} | 耗时: {result.execution.runtime_ms}ms</p>
                        {result.execution.stderr && <pre className="text-rose-400 mt-1 whitespace-pre-wrap">{result.execution.stderr}</pre>}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-600">
                    <p className="text-lg mb-1">等待提交</p>
                    <p className="text-xs">编写代码后点击「提交代码」查看判题结果</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-4"><span className="text-2xl">🏆</span></div>
            <p className="text-slate-400">选择题目或让 AI 生成，开始 ACM 模式练习</p>
          </div>
        </div>
      )}
    </div>
  );
}
