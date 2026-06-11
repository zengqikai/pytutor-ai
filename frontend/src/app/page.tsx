"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Editor from "@monaco-editor/react";
import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";
import { chatAPI, codeAPI } from "@/lib/api";
import { ChatMessage } from "@/components/chat-message";

interface Message {
  role: "user" | "assistant";
  content: string;
  response_type?: string;
  hint_level?: number;
  related_concepts?: string[];
  misconception_id?: string;
  pedagogical_strategy?: string;
}

export default function ChatPage() {
  const router = useRouter();
  const { user, isAuthenticated, loadUser } = useAuthStore();
  const chatStore = useChatStore();
  const [sessions, setSessions] = useState<any[]>([]);
  const activeSession = chatStore.activeSession;
  const messages = chatStore.messages;
  const [input, setInput] = useState("");
  const [sending, set发送ing] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [code, setCode] = useState("print('Hello, Python!')\n");
  const [codeResult, setCodeResult] = useState<any>(null);
  const [runningCode, set运行ningCode] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [customInput, setCustomInput] = useState("");
  const [editorKey, setEditorKey] = useState(0);
  const [reasoningMode, setReasoningMode] = useState(false);
  const [editingSession, setEditingSession] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [menuSession, setMenuSession] = useState<string | null>(null);
  const [pinnedSessions, setPinnedSessions] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ---- Auth & Init ----
  useEffect(() => {
    loadUser();
    if (!isAuthenticated) { router.push("/login"); return; }
    loadSessions();
  }, [isAuthenticated]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const loadSessions = async () => { try { setSessions(await chatAPI.getSessions()); } catch {} };

  const ensureSession = async (): Promise<string> => {
    if (activeSession) return activeSession;
    try {
      const s = await chatAPI.createSession("新的对话");
      setSessions((p) => [s, ...p]); chatStore.setActiveSession(s.id); return s.id;
    } catch (e) { throw e; }
  };
  const newSession = () => { chatStore.setActiveSession(null); chatStore.setMessages([]); };
  const loadSession = async (id: string) => {
    chatStore.setActiveSession(id);
    try { const s = await chatAPI.getSession(id); chatStore.setMessages(s.messages || []); } catch {}
  };

  // ---- Session actions ----
  const startRename = (s: any) => { setMenuSession(null); setEditingSession(s.id); setEditTitle(s.title || ""); };
  const saveRename = async () => {
    if (!editingSession || !editTitle.trim()) { setEditingSession(null); return; }
    try { await chatAPI.renameSession(editingSession, editTitle.trim()); setSessions((p) => p.map((s) => s.id === editingSession ? { ...s, title: editTitle.trim() } : s)); } catch {}
    setEditingSession(null);
  };
  const deleteSession = async (id: string) => {
    setMenuSession(null);
    if (!confirm("确定删除此对话？")) return;
    try { await chatAPI.deleteSession(id); setSessions((p) => p.filter((s) => s.id !== id)); setPinnedSessions((prev) => { const next = new Set(prev); next.delete(id); return next; }); if (activeSession === id) { chatStore.setActiveSession(null); chatStore.setMessages([]); } } catch (e: any) { alert(e.message); }
  };
  const togglePin = (id: string) => { setMenuSession(null); setPinnedSessions((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; }); };

  const sortedSessions = [...sessions].sort((a, b) => {
    const aPin = pinnedSessions.has(a.id) ? 1 : 0; const bPin = pinnedSessions.has(b.id) ? 1 : 0; return bPin - aPin;
  });

  // ---- 发送 message ----
  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const content = input; const userMsg: Message = { role: "user", content };
    chatStore.addMessage(userMsg); setInput(""); set发送ing(true);
    try {
      const sid = await ensureSession();
      const chatRes = await chatAPI.sendMessage(sid, content, reasoningMode ? "deepseek-v4-pro" : undefined);
      const ai = chatRes.ai_response || {};
      chatStore.addMessage({ role: "assistant", content: ai.message || "抱歉，回复生成失败。", response_type: ai.response_type, hint_level: ai.hint_level, related_concepts: ai.related_concepts, misconception_id: ai.misconception_id, pedagogical_strategy: ai.pedagogical_strategy });
      loadSessions();
    } catch (e: any) { chatStore.addMessage({ role: "assistant", content: `Error: ${e.message}` }); }
    finally { set发送ing(false); }
  };

  // ---- Code execution ----
  const runCode = async () => {
    if (!isAuthenticated) { setCodeResult({ stderr: "请先登录后再运行代码" }); return; }
    set运行ningCode(true); setCodeResult(null);
    try {
      const res = await codeAPI.submit(code, undefined, customInput);
      const result = { ...(res.result || res) };
      setCodeResult(result); set运行ningCode(false);
      if (result.stderr && result.status !== "completed") {
        setAnalyzing(true);
        try { const analysis = await codeAPI.analyze(code, result.stderr); setCodeResult((prev: any) => ({ ...prev, error_analysis: analysis })); } catch {}
        setAnalyzing(false);
      }
    } catch (e: any) { setCodeResult({ stderr: `运行失败: ${e.message}` }); set运行ningCode(false); }
  };

  if (!isAuthenticated) return <div className="flex items-center justify-center h-full text-slate-500">Loading...</div>;

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* ====== 左侧会话栏 ====== */}
      <aside className="w-72 glass border-r border-white/[0.06] flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-white/[0.06]">
          <button onClick={newSession}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl text-sm font-medium
              hover:from-indigo-500 hover:to-violet-500 transition-all shadow-lg shadow-indigo-500/15">
            <PlusIcon /> 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {sortedSessions.map((s) => (
            editingSession === s.id ? (
              <input key={s.id} value={editTitle} onChange={(e) => setEditTitle(e.target.value)} onBlur={saveRename}
                onKeyDown={(e) => { if (e.key === "Enter") saveRename(); if (e.key === "Escape") setEditingSession(null); }}
                className="w-full px-3 py-2 rounded-xl text-sm bg-white/[0.06] border border-indigo-500/30 text-white outline-none" autoFocus />
            ) : (
              <div key={s.id} className={`group flex items-center rounded-xl transition-all relative ${activeSession === s.id ? "bg-indigo-500/10" : "hover:bg-white/[0.04]"}`}>
                <button onClick={() => { setMenuSession(null); loadSession(s.id); }}
                  className="flex-1 text-left px-3 py-2.5 text-sm truncate">
                  <span className="flex items-center gap-1.5">
                    {pinnedSessions.has(s.id) && <span className="text-[10px] text-amber-400">📌</span>}
                    <span className={`truncate ${activeSession === s.id ? "text-indigo-300 font-medium" : "text-slate-400"}`}>{s.title || "未命名"}</span>
                  </span>
                </button>
                <button onClick={(e) => { e.stopPropagation(); setMenuSession(menuSession === s.id ? null : s.id); }}
                  className="px-2 py-2.5 text-slate-600 hover:text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity rounded-r-xl flex-shrink-0">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>
                </button>
                {menuSession === s.id && (
                  <>
                    <div className="fixed inset-0 z-30" onClick={() => setMenuSession(null)} />
                    <div className="absolute right-2 top-full mt-1 z-40 glass rounded-xl border border-white/[0.08] py-1 w-36 animate-fade-in shadow-xl">
                      <button onClick={() => startRename(s)} className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.04] flex items-center gap-2">✏️ 重命名</button>
                      <button onClick={() => togglePin(s.id)} className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.04] flex items-center gap-2">{pinnedSessions.has(s.id) ? "📌 取消置顶" : "📌 置顶"}</button>
                      <button onClick={() => deleteSession(s.id)} className="w-full text-left px-4 py-2 text-sm text-rose-400 hover:bg-rose-500/10 flex items-center gap-2">🗑 删除</button>
                    </div>
                  </>
                )}
              </div>
            )
          ))}
        </div>
        <div className="p-4 border-t border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold">{user?.display_name?.[0] || "..."}</div>
            <div className="flex-1 min-w-0"><p className="text-sm font-medium text-slate-300 truncate">{user?.display_name}</p><p className="text-xs text-slate-500">{user?.role === "admin" ? "管理员" : user?.role === "instructor" ? "教师" : "学员"}</p></div>
          </div>
        </div>
      </aside>

      {/* ====== 聊天区 ====== */}
      <div className="flex-1 flex flex-col bg-gradient-to-b from-[#06060f] to-[#0a0a18]">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center animate-fade-in px-4">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-white/[0.06] flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-500/10">
                <span className="text-3xl">🐍</span>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">欢迎来到 PyTutor</h2>
              <p className="text-slate-400 mb-8 max-w-md">你的 AI Python 编程导师。<br/>无论是学习概念还是调试代码，随时问我！</p>
              <div className="flex gap-3 justify-center flex-wrap">
                {["什么是 Python 列表？", "for 循环怎么用？", "帮我写一个函数", "解释什么是变量"].map((q) => (
                  <button key={q} onClick={() => setInput(q)}
                    className="px-4 py-2 glass border-white/[0.08] rounded-full text-sm text-slate-300 hover:border-indigo-500/30 hover:text-indigo-300 transition-all">{q}</button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="max-w-3xl mx-auto space-y-5">
              {messages.map((msg, i) => (
                <ChatMessage key={i} role={msg.role} content={msg.content} hint_level={msg.hint_level} related_concepts={msg.related_concepts} userAvatar={user?.display_name?.[0]}
                  onRunInEditor={(codeStr) => { setCode(codeStr); setShowCode(true); setEditorKey(k => k + 1); }} />
              ))}
              {sending && (
                <div className="flex gap-3 animate-fade-in">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold">AI</div>
                  <div className="glass border-white/[0.06] rounded-xl px-4 py-3">
                    <div className="flex gap-1.5">
                      <span className="w-2 h-2 bg-slate-500 rounded-full animate-dot-pulse" /><span className="w-2 h-2 bg-slate-500 rounded-full animate-dot-pulse delay-200" /><span className="w-2 h-2 bg-slate-500 rounded-full animate-dot-pulse delay-400" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        {/* 输入区 */}
        <div className="border-t border-white/[0.06] glass p-4">
          <div className="max-w-3xl mx-auto space-y-2">
            {/* 模式切换 */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setReasoningMode(false)}
                className={`text-[11px] px-3 py-1 rounded-full font-medium transition-all
                  ${!reasoningMode
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                    : "text-slate-500 hover:text-slate-400"}`}>
                ⚡ CHAT
              </button>
              <button
                onClick={() => setReasoningMode(true)}
                className={`text-[11px] px-3 py-1 rounded-full font-medium transition-all
                  ${reasoningMode
                    ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                    : "text-slate-500 hover:text-slate-400"}`}>
                🧠 REASONING
              </button>
            </div>
          <div className="flex gap-3 items-stretch">
            <button onClick={() => setShowCode(!showCode)}
              className={`flex items-center gap-1.5 px-4 rounded-xl border transition-all flex-shrink-0 text-sm font-medium
                ${showCode ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-400" : "border-white/[0.08] text-slate-400 hover:text-indigo-400 hover:border-indigo-500/30"}`}>
              <CodeIcon /> 编辑器
            </button>
            <div className="flex-1 relative">
              <textarea value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                placeholder="输入你的 Python 问题... (Enter 发送)"
                rows={1}
                className="neon w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 resize-none outline-none transition-all"
                style={{ minHeight: "44px", maxHeight: "120px" }}
                onInput={(e) => { const t = e.target as HTMLTextAreaElement; t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 120) + "px"; }} />
            </div>
            <button onClick={sendMessage} disabled={sending || !input.trim()}
              className="glow-hover flex items-center px-6 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl text-sm font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-30 transition-all flex-shrink-0">
              发送
            </button>
          </div>
          </div>
        </div>
      </div>

      {/* ====== 代码面板 ====== */}
      {showCode && (
        <aside className="w-[420px] border-l border-white/[0.06] bg-[#0a0a14] flex flex-col animate-slide-in flex-shrink-0">
          <div className="shrink-0 px-5 py-3 border-b border-white/[0.06] flex items-center justify-between">
            <span className="text-sm font-medium text-slate-300">Python 编辑器</span>
            <div className="flex items-center gap-2">
              <button onClick={() => { setCode("print('Hello, Python!')\n"); setCodeResult(null); }} className="text-xs text-slate-500 hover:text-slate-300 px-2 py-1 rounded transition-colors">清空</button>
              <button onClick={() => {
                  const blob = new Blob([code], { type: "text/x-python" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url; a.download = `pytutor_${Date.now()}.py`;
                  a.click(); URL.revokeObjectURL(url);
                }}
                className="text-xs text-sky-400 hover:text-sky-300 px-2 py-1 rounded transition-colors">
                ⬇ 下载 .py
              </button>
              <button onClick={runCode} disabled={runningCode}
                className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-1.5 rounded-lg text-xs font-medium transition-colors">
                {runningCode ? "..." : "▶"} 运行
              </button>
            </div>
          </div>
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex-1 min-h-0">
              <Editor key={editorKey} height="100%" defaultLanguage="python" theme="vs-dark" value={code} onChange={(v) => setCode(v || "")}
                options={{ fontSize: 14, fontFamily: "var(--font-geist-mono), monospace", minimap: { enabled: false }, scrollBeyondLastLine: false, lineNumbers: "on", padding: { top: 12 }, automaticLayout: true }} />
            </div>
            {/* Stdin 输入 */}
            <div className="border-t border-white/[0.06] px-3 py-2 bg-[#060610]">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex-shrink-0">输入</span>
                <input
                  value={customInput}
                  onChange={(e) => setCustomInput(e.target.value)}
                  placeholder="stdin（如果代码用 input()）"
                  className="flex-1 bg-black/40 border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-green-300 font-mono outline-none focus:border-emerald-500/30 placeholder:text-slate-600"
                />
              </div>
            </div>
            <div className="flex-1 flex flex-col border-t-2 border-white/[0.06] bg-[#060610] min-h-0 overflow-y-auto">
              <div className="shrink-0 px-5 py-2 border-b border-white/[0.04] flex items-center justify-between">
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">运行结果</p>
                {codeResult && <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${codeResult.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : codeResult.status === "blocked" ? "bg-amber-500/10 text-amber-400" : "bg-rose-500/10 text-rose-400"}`}>{codeResult.status}</span>}
              </div>
              <div className="flex-1 p-5 overflow-y-auto space-y-4">
                {runningCode ? (
                  <div className="flex items-center gap-2 text-slate-400 text-sm"><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2"/><path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg> 执行中...</div>
                ) : codeResult ? (
                  <>
                    <运行结果Block label="stdout" color="emerald" content={codeResult.stdout || "(no output)"} />
                    <运行结果Block label="stderr" color="rose" content={codeResult.stderr || "(no errors)"} />
                    <div>
                      <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider mb-1.5">AI 错误分析</p>
                      {analyzing ? (
                        <div className="flex items-center gap-3 bg-amber-500/5 border border-amber-500/10 rounded-lg p-4">
                          <svg className="animate-spin w-4 h-4 text-amber-400" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2"/><path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg>
                          <span className="text-sm text-amber-300/60">AI 正在分析错误原因...</span>
                        </div>
                      ) : codeResult.error_analysis ? (
                        <div className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-4">
                          <p className="text-amber-200/80 text-sm leading-relaxed">{codeResult.error_analysis.explanation}</p>
                          {codeResult.error_analysis.concepts?.length > 0 && (
                            <div className="flex gap-1.5 mt-3 flex-wrap">{codeResult.error_analysis.concepts.map((c: string) => <span key={c} className="text-[10px] bg-amber-500/10 text-amber-300 px-2.5 py-1 rounded-full">{c}</span>)}</div>
                          )}
                        </div>
                      ) : codeResult.stderr ? <div className="text-sm text-slate-500 bg-white/[0.02] rounded-lg p-4 italic">无错误分析</div> : <div className="text-sm text-slate-500 bg-white/[0.02] rounded-lg p-4 italic">代码正常，无需分析</div>}
                    </div>
                    {codeResult.runtime_ms && <p className="text-[10px] text-slate-600 text-right">{codeResult.runtime_ms}ms</p>}
                  </>
                ) : (
                  <div className="h-full flex items-center justify-center text-center"><div><p className="text-4xl mb-3 opacity-30">▶</p><p className="text-sm text-slate-600">在上方编写代码</p><p className="text-xs text-slate-700 mt-1">Click <span className="text-emerald-500">运行</span> to execute</p></div></div>
                )}
              </div>
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}

function 运行结果Block({ label, color, content }: { label: string; color: string; content: string }) {
  const colors: any = { emerald: "text-emerald-400 border-emerald-500/10 bg-emerald-500/5", rose: "text-rose-400 border-rose-500/10 bg-rose-500/5" };
  return (
    <div>
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">{label}</p>
      <pre className={`text-sm whitespace-pre-wrap font-mono leading-relaxed rounded-lg p-3 border ${colors[color] || "text-slate-400"}`}>{content}</pre>
    </div>
  );
}

function PlusIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>; }
function CodeIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>; }
