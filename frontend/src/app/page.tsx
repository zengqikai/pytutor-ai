"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Editor from "@monaco-editor/react";
import { useAuthStore } from "@/stores/auth";
import { chatAPI, agentAPI, codeAPI } from "@/lib/api";
import { ChatMessage } from "@/components/chat-message";

interface Message {
  role: "user" | "assistant";
  content: string;
  response_type?: string;
  hint_level?: number;
  related_concepts?: string[];
}

export default function ChatPage() {
  const router = useRouter();
  const { user, isAuthenticated, loadUser } = useAuthStore();
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [code, setCode] = useState("print('Hello, Python!')\n");
  const [codeResult, setCodeResult] = useState<any>(null);
  const [runningCode, setRunningCode] = useState(false);
  const [editingSession, setEditingSession] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [menuSession, setMenuSession] = useState<string | null>(null);
  const [pinnedSessions, setPinnedSessions] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadUser();
    if (!isAuthenticated) { router.push("/login"); return; }
    loadSessions();
  }, [isAuthenticated]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const loadSessions = async () => {
    try { setSessions(await chatAPI.getSessions()); } catch {}
  };

  // 创建新会话（自动）
  const ensureSession = async (): Promise<string> => {
    if (activeSession) return activeSession;
    try {
      const s = await chatAPI.createSession("新的对话");
      setSessions((p) => [s, ...p]);
      setActiveSession(s.id);
      return s.id;
    } catch (e) { throw e; }
  };

  const newSession = () => { setActiveSession(null); setMessages([]); };

  const loadSession = async (id: string) => {
    setActiveSession(id);
    try { const s = await chatAPI.getSession(id); setMessages(s.messages || []); } catch {}
  };

  const startRename = (s: any) => {
    setMenuSession(null);
    setEditingSession(s.id);
    setEditTitle(s.title || "");
  };

  const saveRename = async () => {
    if (!editingSession || !editTitle.trim()) { setEditingSession(null); return; }
    try {
      await chatAPI.renameSession(editingSession, editTitle.trim());
      setSessions((p) => p.map((s) => s.id === editingSession ? { ...s, title: editTitle.trim() } : s));
    } catch {}
    setEditingSession(null);
  };

  const deleteSession = async (id: string) => {
    setMenuSession(null);
    if (!confirm("确定删除此对话？")) return;
    try {
      await chatAPI.deleteSession(id);
      setSessions((p) => p.filter((s) => s.id !== id));
      setPinnedSessions((prev) => { const next = new Set(prev); next.delete(id); return next; });
      if (activeSession === id) { setActiveSession(null); setMessages([]); }
    } catch (e: any) { alert(e.message); }
  };

  const togglePin = (id: string) => {
    setMenuSession(null);
    setPinnedSessions((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // 排序：置顶在前，其余按原顺序
  const sortedSessions = [...sessions].sort((a, b) => {
    const aPin = pinnedSessions.has(a.id) ? 1 : 0;
    const bPin = pinnedSessions.has(b.id) ? 1 : 0;
    return bPin - aPin;
  });

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const content = input;
    const userMsg: Message = { role: "user", content };
    setMessages((p) => [...p, userMsg]); setInput(""); setSending(true);

    try {
      // 确保有活跃会话
      const sid = await ensureSession();

      // 1. 通过 Chat API 保存消息并获取 AI 回复（保存历史）
      const chatRes = await chatAPI.sendMessage(sid, content);
      const ai = chatRes.ai_response || {};

      setMessages((p) => [...p, {
        role: "assistant",
        content: ai.message || "抱歉，回复生成失败。",
        response_type: ai.response_type,
        hint_level: ai.hint_level,
        related_concepts: ai.related_concepts,
      }]);

      // 2. 刷新会话列表（标题可能已更新）
      loadSessions();
    } catch (e: any) {
      setMessages((p) => [...p, { role: "assistant", content: `❌ ${e.message}` }]);
    } finally { setSending(false); }
  };

  const runCode = async () => {
    if (!isAuthenticated) {
      setCodeResult({ stderr: "请先登录后再运行代码" });
      return;
    }
    setRunningCode(true);
    setCodeResult(null);
    try {
      const res = await codeAPI.submit(code);
      // 合并 result 和顶层的 error_analysis
      setCodeResult({ ...(res.result || res), error_analysis: res.error_analysis });
    } catch (e: any) {
      setCodeResult({ stderr: `运行失败: ${e.message}` });
    } finally {
      setRunningCode(false);
    }
  };

  if (!isAuthenticated) return <div className="flex items-center justify-center h-full text-slate-400">加载中...</div>;

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* 左侧会话栏 */}
      <aside className="w-72 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-4 border-b border-slate-100">
          <button onClick={newSession}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl text-sm font-medium
              hover:from-indigo-700 hover:to-violet-700 transition-all shadow-sm shadow-indigo-200">
            <PlusIcon /> 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {sortedSessions.map((s) => (
            editingSession === s.id ? (
              <input key={s.id}
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onBlur={saveRename}
                onKeyDown={(e) => { if (e.key === "Enter") saveRename(); if (e.key === "Escape") setEditingSession(null); }}
                className="w-full px-3 py-2 rounded-xl text-sm border border-indigo-300 outline-none focus:ring-2 focus:ring-indigo-100 bg-white"
                autoFocus
                onClick={(e) => e.stopPropagation()} />
            ) : (
              <div key={s.id}
                className={`group flex items-center rounded-xl transition-all relative
                  ${activeSession === s.id ? "bg-indigo-50 shadow-sm" : "hover:bg-slate-50"}`}>
                <button onClick={() => { setMenuSession(null); loadSession(s.id); }}
                  className="flex-1 text-left px-3 py-2.5 text-sm truncate">
                  <span className="flex items-center gap-1.5">
                    {pinnedSessions.has(s.id) && <span className="text-[10px] text-amber-500 flex-shrink-0">📌</span>}
                    <span className={`truncate ${activeSession === s.id ? "text-indigo-700 font-medium" : "text-slate-600"}`}>
                      {s.title || "未命名对话"}
                    </span>
                  </span>
                </button>
                <button onClick={(e) => { e.stopPropagation(); setMenuSession(menuSession === s.id ? null : s.id); }}
                  className="px-2 py-2.5 text-slate-400 hover:text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity rounded-r-xl hover:bg-slate-100 flex-shrink-0">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>
                </button>
                {/* 下拉菜单 */}
                {menuSession === s.id && (
                  <>
                    <div className="fixed inset-0 z-30" onClick={() => setMenuSession(null)} />
                    <div className="absolute right-2 top-full mt-1 z-40 bg-white rounded-xl shadow-lg border border-slate-200 py-1 w-36 animate-fade-in">
                      <button onClick={() => startRename(s)}
                        className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                        ✏️ 重命名
                      </button>
                      <button onClick={() => togglePin(s.id)}
                        className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                        {pinnedSessions.has(s.id) ? "📌 取消置顶" : "📌 置顶"}
                      </button>
                      <button onClick={() => deleteSession(s.id)}
                        className="w-full text-left px-4 py-2 text-sm text-rose-600 hover:bg-rose-50 flex items-center gap-2">
                        🗑 删除
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          ))}
          {sessions.length === 0 && (
            <p className="text-center text-xs text-slate-400 py-8">暂无对话，发送消息开始</p>
          )}
        </div>
        <div className="p-4 border-t border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-xs font-bold">
              {user?.display_name?.[0] || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.display_name}</p>
              <p className="text-xs text-slate-400">Python 学习者</p>
            </div>
          </div>
        </div>
      </aside>

      {/* 中间聊天区 */}
      <div className="flex-1 flex flex-col bg-gradient-to-b from-slate-50 to-white">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center animate-fade-in px-4">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center mx-auto mb-6 shadow-sm">
                <span className="text-3xl">🐍</span>
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-2">欢迎来到 PyTutor</h2>
              <p className="text-slate-500 mb-8 max-w-md">我是你的 AI Python 编程导师。<br/>无论你想学习基础概念还是调试代码，随时问我！</p>
              <div className="flex gap-3 justify-center flex-wrap">
                {["什么是 Python 列表？", "for 循环怎么用？", "帮我写一个函数", "解释什么是变量"].map((q) => (
                  <button key={q} onClick={() => setInput(q)}
                    className="px-4 py-2 bg-white border border-slate-200 rounded-full text-sm text-slate-600 hover:border-indigo-300 hover:text-indigo-600 transition-all shadow-sm">{q}</button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="max-w-3xl mx-auto space-y-5">
              {messages.map((msg, i) => (
                <ChatMessage key={i} role={msg.role} content={msg.content}
                  hint_level={msg.hint_level} related_concepts={msg.related_concepts}
                  userAvatar={user?.display_name?.[0]} />
              ))}
              {sending && (
                <div className="flex gap-3 animate-fade-in">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white text-sm font-bold shadow-sm">AI</div>
                  <div className="bg-white border border-slate-200/60 rounded-2xl px-5 py-3.5 shadow-sm">
                    <div className="flex gap-1.5">
                      <span className="w-2 h-2 bg-slate-300 rounded-full animate-pulse-dot" />
                      <span className="w-2 h-2 bg-slate-300 rounded-full animate-pulse-dot" style={{ animationDelay: "0.2s" }} />
                      <span className="w-2 h-2 bg-slate-300 rounded-full animate-pulse-dot" style={{ animationDelay: "0.4s" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        {/* 输入区 */}
        <div className="border-t border-slate-200/60 bg-white/80 backdrop-blur-sm p-4">
          <div className="max-w-3xl mx-auto flex gap-3 items-end">
            <button onClick={() => setShowCode(!showCode)}
              className={`px-3 py-2 rounded-xl border transition-all flex-shrink-0 flex items-center gap-1.5 text-sm font-medium
                ${showCode
                  ? "bg-indigo-50 border-indigo-200 text-indigo-600"
                  : "border-slate-200 text-slate-400 hover:text-indigo-600 hover:border-indigo-200"}`}
              title={showCode ? "关闭代码编辑器" : "打开 Python 代码编辑器"}>
              <CodeIcon /> {showCode ? "关闭" : "编辑器"}
            </button>
            <div className="flex-1 relative">
              <textarea value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                placeholder="输入你的 Python 问题... (Enter 发送)"
                rows={1}
                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm resize-none outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 transition-all"
                style={{ minHeight: "44px", maxHeight: "120px" }}
                onInput={(e) => {
                  const t = e.target as HTMLTextAreaElement;
                  t.style.height = "auto";
                  t.style.height = Math.min(t.scrollHeight, 120) + "px";
                }} />
            </div>
            <button onClick={sendMessage} disabled={sending || !input.trim()}
              className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl text-sm font-medium
                hover:from-indigo-700 hover:to-violet-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm shadow-indigo-200 flex-shrink-0">
              发送
            </button>
          </div>
        </div>
      </div>

      {/* 右侧代码面板 */}
      {showCode && (
        <aside className="w-[420px] border-l border-slate-200 bg-slate-900 flex flex-col animate-slide-in">
          {/* 顶部工具栏 */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-700">
            <span className="text-sm font-medium text-slate-300 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" /> Python 编辑器
            </span>
            <div className="flex gap-2">
              <button onClick={() => { setCode("print('Hello, Python!')\n"); setCodeResult(null); }}
                className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded transition-colors">清空</button>
              <button onClick={runCode} disabled={runningCode}
                className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors">
                {runningCode ? "⏳ 运行中..." : "▶ 运行"}
              </button>
            </div>
          </div>

          {/* 编辑器 */}
          <div className="h-[45%] border-b border-slate-700">
            <Editor height="100%" defaultLanguage="python" theme="vs-dark" value={code}
              onChange={(v) => setCode(v || "")}
              options={{ fontSize: 14, fontFamily: "var(--font-geist-mono), monospace", minimap: { enabled: false },
                scrollBeyondLastLine: false, lineNumbers: "on", padding: { top: 8 }, automaticLayout: true }} />
          </div>

          {/* 运行结果 —— 永远显示 */}
          <div className="flex-1 flex flex-col bg-slate-950 overflow-y-auto">
            <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">运行结果</p>
              {codeResult && (
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full
                  ${codeResult.status === "completed" ? "bg-emerald-900/50 text-emerald-400" :
                    codeResult.status === "blocked" ? "bg-amber-900/50 text-amber-400" :
                    "bg-rose-900/50 text-rose-400"}`}>
                  {codeResult.status}
                </span>
              )}
            </div>
            <div className="flex-1 p-4">
              {runningCode ? (
                <div className="flex items-center gap-2 text-slate-500">
                  <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse-dot" />
                  <span className="text-sm">代码执行中...</span>
                </div>
              ) : codeResult ? (
                <div className="space-y-3">
                  {/* 错误分析（AI 自然语言解释） */}
                  {codeResult.error_analysis && (
                    <div className="bg-amber-950/20 border border-amber-500/20 rounded-lg p-3">
                      <p className="text-[10px] font-medium text-amber-400/80 uppercase tracking-wider mb-1.5">
                        AI 错误分析
                      </p>
                      <p className="text-amber-200/90 text-sm leading-relaxed">
                        {codeResult.error_analysis.explanation}
                      </p>
                      {codeResult.error_analysis.concepts?.length > 0 && (
                        <div className="flex gap-1.5 mt-2 flex-wrap">
                          {codeResult.error_analysis.concepts.map((c: string) => (
                            <span key={c} className="text-[10px] bg-amber-900/40 text-amber-300 px-2 py-0.5 rounded-full">{c}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {codeResult.stdout ? (
                    <div>
                      <p className="text-[10px] font-medium text-emerald-500/70 uppercase tracking-wider mb-1">标准输出 stdout</p>
                      <pre className="text-emerald-300 text-sm whitespace-pre-wrap font-mono leading-relaxed bg-emerald-950/30 rounded-lg p-3">{codeResult.stdout}</pre>
                    </div>
                  ) : null}
                  {codeResult.stderr ? (
                    <div>
                      <p className="text-[10px] font-medium text-rose-500/70 uppercase tracking-wider mb-1">错误输出 stderr</p>
                      <pre className="text-rose-300 text-sm whitespace-pre-wrap font-mono leading-relaxed bg-rose-950/30 rounded-lg p-3">{codeResult.stderr}</pre>
                    </div>
                  ) : null}
                  {codeResult.runtime_ms && (
                    <p className="text-[10px] text-slate-500">耗时: {codeResult.runtime_ms}ms</p>
                  )}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-center">
                  <div>
                    <p className="text-4xl mb-3">▶</p>
                    <p className="text-sm text-slate-500">在上方编写代码</p>
                    <p className="text-xs text-slate-600 mt-1">点击 <span className="text-emerald-500 font-medium">运行</span> 查看输出结果</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </aside>
      )}

    </div>
  );
}

function PlusIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>;
}
function CodeIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>;
}
