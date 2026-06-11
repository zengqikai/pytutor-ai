"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import Editor from "@monaco-editor/react";
import { useAuthStore } from "@/stores/auth";
import { useExerciseStore } from "@/stores/exercise";
import { exerciseAPI } from "@/lib/api";

const diffLabels: Record<number, string> = { 1: "入门", 2: "基础", 3: "进阶", 4: "困难", 5: "挑战" };

export default function ExercisesPage() {
  const { loadUser } = useAuthStore();
  const store = useExerciseStore();

  const [exercises, setExercises] = useState<any[]>([]);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [testRunning, setTestRunning] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [displayedHintLevel, setDisplayedHintLevel] = useState(0);
  const [passedIds, setPassedIds] = useState<Set<string>>(new Set()); // 已通过的题目 ID 集合

  useEffect(() => { loadUser(); loadExercises(); loadPassed(); }, []);
  useEffect(() => { loadExercises(); }, [store.difficulty]);

  const loadPassed = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      const r = await fetch("http://localhost:8000/api/v1/profile/me/passed-ids", { headers: { Authorization: `Bearer ${token}` } });
      const data = await r.json();
      setPassedIds(new Set(data.ids || []));
    } catch {}
  };

  const loadExercises = async () => { try { setExercises(await exerciseAPI.list(store.difficulty)); } catch {} };

  const selectExercise = (ex: any) => {
    // 同一道题不重置（保留编辑中的代码）
    const sameExercise = store.selected?.id === ex.id;
    store.setSelected(ex);
    store.setResult(null);
    store.setTestResult(null);
    store.setHintText("");
    if (!sameExercise) store.setUserCode("# 在此编写你的代码\n");  // 换题重置
    store.setCustomInput("");
    store.setHintLevel(1);
    setDisplayedHintLevel(0);
    store.setShowSolution(false);  // 重置答案查看状态
    store.setShowSolution(false);
  };

  const generateExercise = async () => {
    setGenerating(true);
    try {
      const res = await exerciseAPI.generate({ difficulty: store.difficulty, count: 1 });
      if (res.exercises?.length) {
        setExercises((p) => [res.exercises[0], ...p]);
        selectExercise(res.exercises[0]);
      }
    } catch (e: any) { alert(e.message); } finally { setGenerating(false); }
  };

  const submitAnswer = async () => {
    if (!store.selected || !store.userCode.trim()) return;
    setSubmitting(true); store.setResult(null);
    try {
      const token = localStorage.getItem("auth_token");
      const res = await fetch(`http://localhost:8000/api/v1/exercises/${store.selected.id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          code: store.userCode,
          used_hints: displayedHintLevel,       // 使用了多少次提示
          viewed_solution: store.showSolution,   // 是否查看了答案
        }),
      });
      store.setResult(await res.json());
      loadPassed();
    } catch (e: any) { alert(e.message); } finally { setSubmitting(false); }
  };

  const requestHint = async () => {
    if (!store.selected) return;
    setHintLoading(true);
    try {
      const token = localStorage.getItem("auth_token");
      const res = await fetch(`http://localhost:8000/api/v1/exercises/${store.selected.id}/hint`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          hint_level: store.hintLevel,
          code: store.userCode,
          failed_info: store.result?.test_results?.details?.filter((d: any) => !d.passed).map((d: any) => d.description).join("; ") || "",
        }),
      });
      const d = await res.json();
      const currentLevel = store.hintLevel;
      store.setHintText(d.hint || "");
      setDisplayedHintLevel(currentLevel);  // 记录本次显示的等级
      // 两次后禁用：level 2 点完后设为 3（> 2 触发 disabled）
      store.setHintLevel(currentLevel >= 2 ? 3 : currentLevel + 1);
    } catch (e: any) { store.setHintText("获取提示失败"); }
    finally { setHintLoading(false); }
  };

  const viewSolution = async () => {
    if (!store.selected) return;
    try {
      const token = localStorage.getItem("auth_token");
      const res = await fetch(`http://localhost:8000/api/v1/exercises/${store.selected.id}/solution`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await res.json();
      store.setSolutionText(d.solution || "暂无");
      store.setShowSolution(true);
    } catch { store.setSolutionText("获取失败"); store.setShowSolution(true); }
  };

  const runTest = async () => {
    if (!store.userCode.trim()) return;
    setTestRunning(true); store.setTestResult(null);
    try {
      const { codeAPI } = await import("@/lib/api");
      const res = await codeAPI.submit(store.userCode, undefined, store.customInput);
      const exec = res.result || res;
      store.setTestResult({ stdout: exec.stdout || "(无输出)", stderr: exec.stderr || "", status: exec.status, runtime_ms: exec.runtime_ms });
    } catch (e: any) { store.setTestResult({ stderr: String(e.message) }); }
    finally { setTestRunning(false); }
  };

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* 左侧题库 */}
      <aside className="w-72 glass border-r border-white/[0.06] flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-white/[0.06]">
          <h2 className="font-bold text-base text-white mb-3">题库</h2>
          <div className="flex gap-2 mb-3">
            <select value={store.difficulty} onChange={(e) => store.setDifficulty(Number(e.target.value))}
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
          {exercises.length === 0 && (
            <div className="text-center py-8 text-slate-500 text-xs">
              <p>当前难度暂无题目</p>
              <p className="mt-1">点击下方"AI 生成题目"创建</p>
            </div>
          )}
          {exercises.map((ex) => {
            const isDone = passedIds.has(ex.id);
            return (
            <button key={ex.id} onClick={() => selectExercise(ex)}
              className={`w-full text-left p-3 rounded-xl transition-all border ${store.selected?.id === ex.id ? "border-indigo-500/30 bg-indigo-500/10" : "border-white/[0.04] hover:border-white/[0.08]"}`}>
              <p className="font-semibold text-sm text-slate-200 truncate mb-1">{isDone && "✅ "}{ex.title}</p>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-slate-400 font-medium">{diffLabels[ex.difficulty]}</span>
            </button>
          )})}
        </div>
      </aside>

      {/* 右侧：题目 + 代码 + 结果 */}
      {store.selected ? (
        <div className="flex-1 flex">
          {/* 题目描述 + 帮助区 */}
          <div className="flex-1 overflow-y-auto border-r border-white/[0.06]">
            <div className="p-6">
              <div className="mb-6">
                <h1 className="text-xl font-bold text-white mb-2">{store.selected.title}</h1>
                <div className="flex items-center gap-3">
                  <span className="text-xs px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-slate-400">{"★".repeat(store.selected.difficulty)} {diffLabels[store.selected.difficulty]}</span>
                  <span className="text-xs text-slate-500">{store.selected.concepts || "通用"}</span>
                </div>
              </div>
              <div className="glass rounded-2xl p-6 border-white/[0.06] prose-dark mb-6"><ReactMarkdown>{store.selected.description}</ReactMarkdown></div>
              {store.selected.example_input && (
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="glass rounded-xl p-5 border-white/[0.06]"><p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">样例输入</p><pre className="text-sm text-emerald-300 font-mono whitespace-pre-wrap bg-emerald-500/5 rounded-lg p-3">{store.selected.example_input}</pre></div>
                  <div className="glass rounded-xl p-5 border-white/[0.06]"><p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">样例输出</p><pre className="text-sm text-emerald-300 font-mono whitespace-pre-wrap bg-emerald-500/5 rounded-lg p-3">{store.selected.example_output}</pre></div>
                </div>
              )}

              {/* 帮助按钮区 —— 始终可用 */}
              <div className="space-y-4 pt-4 border-t border-white/[0.04]">
                <div className="flex gap-2">
                  <button onClick={requestHint} disabled={hintLoading || store.hintLevel >= 3} className="text-xs px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-lg hover:bg-amber-500/20 transition-colors disabled:opacity-30">{hintLoading ? "生成中..." : store.hintLevel >= 3 ? "💡 提示已用完" : displayedHintLevel === 0 ? "💡 提示" : `💡 提示 (${displayedHintLevel}/2)`}</button>
                  <button onClick={viewSolution} className="text-xs px-3 py-1.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-lg hover:bg-indigo-500/20 transition-colors">📖 参考答案</button>
                </div>
                {store.result && store.result.test_results && (
                  <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">判题注释</p>
                    <p className="text-sm text-slate-400">
                      {store.result.test_results.all_passed
                        ? `✅ 全部通过 ${store.result.test_results.passed}/${store.result.test_results.total} 个测试用例`
                        : `❌ 通过 ${store.result.test_results.passed}/${store.result.test_results.total}，还有 ${store.result.test_results.total - store.result.test_results.passed} 个用例未通过`}
                    </p>
                  </div>
                )}
                {store.hintText && (
                  <div className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-4 text-sm text-amber-200/80 leading-relaxed animate-fade-in">
                    <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider mb-1.5">💡 Level {displayedHintLevel} 提示</p>{store.hintText}
                  </div>
                )}
                {store.showSolution && (
                  <div className="bg-indigo-500/5 border border-indigo-500/10 rounded-lg p-4 animate-fade-in">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-[10px] font-semibold text-indigo-400/80 uppercase tracking-wider">📖 参考答案</p>
                      <div className="flex items-center gap-2">
                        <button onClick={() => navigator.clipboard.writeText(store.solutionText)} className="text-xs text-slate-400 hover:text-white px-2 py-0.5 rounded transition-colors">📋 复制</button>
                        <button onClick={() => store.setShowSolution(false)} className="text-xs text-slate-500 hover:text-slate-300">收起</button>
                      </div>
                    </div>
                    <pre className="text-sm text-emerald-300 font-mono whitespace-pre-wrap leading-relaxed bg-emerald-500/5 rounded-lg p-3">{store.solutionText}</pre>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 代码 + 提交 + 结果 */}
          <div className="w-[580px] flex flex-col flex-shrink-0">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
              <span className="text-sm font-medium text-slate-300">代码编辑器</span>
              <div className="flex gap-2">
                <button onClick={runTest} disabled={testRunning} className="px-3 py-1.5 bg-slate-700 text-white rounded-lg text-xs font-medium hover:bg-slate-600 disabled:opacity-40 transition-all">{testRunning ? "运行中..." : "▶ 运行测试"}</button>
                <button onClick={submitAnswer} disabled={submitting} className="glow-hover px-4 py-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg text-xs font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40 transition-all">{submitting ? "判题中..." : "提交判题"}</button>
              </div>
            </div>
            <div style={{ height: "45%" }}>
              <Editor height="100%" defaultLanguage="python" theme="vs-dark" value={store.userCode}
                onChange={(v) => store.setUserCode(v || "")}
                options={{ fontSize: 14, fontFamily: "var(--font-geist-mono), monospace", minimap: { enabled: false }, scrollBeyondLastLine: false, lineNumbers: "on", padding: { top: 8 }, automaticLayout: true }} />
            </div>
            {/* 自定义输入 + 自测 */}
            <div className="border-t border-white/[0.06]">
              <div className="px-4 py-2 border-b border-white/[0.04]"><p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">自定义输入（模拟 stdin）</p></div>
              <textarea value={store.customInput} onChange={(e) => store.setCustomInput(e.target.value)}
                placeholder="在这里输入测试数据..."
                className="w-full bg-[#0a0a14] border-0 text-green-300 text-xs font-mono p-3 resize-none outline-none h-16" />
              {store.testResult && (
                <div className="border-t border-white/[0.04]">
                  <div className="px-4 py-2 border-b border-white/[0.04] flex items-center justify-between">
                    <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">自测输出</p>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${store.testResult.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>{store.testResult.status}</span>
                  </div>
                  <div className="p-3 space-y-2">
                    {store.testResult.stdout && <div><p className="text-[10px] text-slate-600 mb-1">stdout</p><pre className="text-emerald-400 text-xs whitespace-pre-wrap font-mono">{store.testResult.stdout}</pre></div>}
                    {store.testResult.stderr && <div><p className="text-[10px] text-slate-600 mb-1">stderr</p><pre className="text-rose-400 text-xs whitespace-pre-wrap font-mono">{store.testResult.stderr}</pre></div>}
                  </div>
                </div>
              )}
            </div>
            {/* 判题结果 */}
            <div className="border-t border-white/[0.06] bg-[#060610] max-h-[40%] overflow-y-auto">
              <div className="px-4 py-2 border-b border-white/[0.04]"><p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">判题结果</p></div>
              <div className="p-4">
                {store.result ? (
                  <div className="space-y-4">
                    <div className={`flex items-center gap-3 p-4 rounded-xl ${store.result.test_results?.passed === store.result.test_results?.total ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-rose-500/10 border border-rose-500/20"}`}>
                      <span className="text-2xl">{store.result.test_results?.passed === store.result.test_results?.total ? "✅" : "❌"}</span>
                      <div><p className={`font-bold ${store.result.test_results?.passed === store.result.test_results?.total ? "text-emerald-400" : "text-rose-400"}`}>{store.result.test_results?.passed === store.result.test_results?.total ? "Accepted" : "Wrong Answer"}</p>
                      <p className="text-sm text-slate-400">{store.result.test_results?.passed}/{store.result.test_results?.total} 测试用例通过</p>
                      {store.result.score_pct > 0 && (
                        <p className="text-xs mt-1">{store.result.score_label} <span className="text-slate-500">（独立分 {store.result.score_pct}%）</span></p>
                      )}</div>
                    </div>
                    {store.result.test_results?.details?.map((tc: any, i: number) => (
                      <div key={i} className={`p-3 rounded-lg border ${tc.passed ? "bg-emerald-500/5 border-emerald-500/10" : "bg-rose-500/5 border-rose-500/10"}`}>
                        <div className="flex items-center gap-2 mb-1"><span className={tc.passed ? "text-emerald-400" : "text-rose-400"}>{tc.passed ? "✓" : "✗"}</span><span className="text-sm font-medium text-slate-300">{tc.description || `测试用例 ${i + 1}`}</span>{tc.is_hidden && <span className="text-[10px] text-slate-600 bg-white/[0.04] px-1.5 py-0.5 rounded">隐藏</span>}</div>
                        {!tc.passed && !tc.is_hidden && (<div className="mt-2 space-y-1 text-xs"><div><span className="text-slate-500">期望：</span><code className="text-emerald-400">{tc.expected}</code></div><div><span className="text-slate-500">实际：</span><code className="text-rose-400">{tc.got}</code></div></div>)}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-600"><p className="text-lg mb-1">等待提交</p><p className="text-xs">编写代码后点击「提交判题」查看结果</p></div>
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
