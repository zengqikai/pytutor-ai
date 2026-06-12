"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Editor from "@monaco-editor/react";
import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";
import { chatAPI, codeAPI, getToken } from "@/lib/api";
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
  const [sending, setSending] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [code, setCode] = useState("print('Hello, Python!')\n");
  const [codeResult, setCodeResult] = useState<any>(null);
  const [runningCode, setRunningCode] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [editorKey, setEditorKey] = useState(0);
  const [reasoningMode, setReasoningMode] = useState(false);
  const [editingSession, setEditingSession] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [menuSession, setMenuSession] = useState<string | null>(null);
  const [pinnedSessions, setPinnedSessions] = useState<Set<string>>(new Set());
  const [customInput, setCustomInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { loadUser(); loadSessions(); }, []);
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

  const startRename = (s: any) => { setMenuSession(null); setEditingSession(s.id); setEditTitle(s.title || ""); };
  const saveRename = async () => {
    if (!editingSession || !editTitle.trim()) { setEditingSession(null); return; }
    try { await chatAPI.renameSession(editingSession, editTitle.trim()); setSessions((p) => p.map((s) => s.id === editingSession ? { ...s, title: editTitle.trim() } : s)); } catch {}
    setEditingSession(null);
  };
  const deleteSession = async (id: string) => { /* unchanged */ };
  const togglePin = (id: string) => { setMenuSession(null); setPinnedSessions((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; }); };

  const sortedSessions = [...sessions].sort((a, b) => {
    const aPin = pinnedSessions.has(a.id) ? 1 : 0; const bPin = pinnedSessions.has(b.id) ? 1 : 0; return bPin - aPin;
  });

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const content = input; const userMsg: Message = { role: "user", content };
    chatStore.addMessage(userMsg); setInput(""); setSending(true);
    try {
      const sid = await ensureSession();
      const chatRes = await chatAPI.sendMessage(sid, content, reasoningMode ? "deepseek-v4-pro" : undefined);
      const ai = chatRes.ai_response || {};
      chatStore.addMessage({ role: "assistant", content: ai.message || "抱歉，回复生成失败。", response_type: ai.response_type, hint_level: ai.hint_level, related_concepts: ai.related_concepts, misconception_id: ai.misconception_id, pedagogical_strategy: ai.pedagogical_strategy });
      loadSessions();
    } catch (e: any) { chatStore.addMessage({ role: "assistant", content: `Error: ${e.message}` }); }
    finally { setSending(false); }
  };

  const runCode = async () => {
    if (!isAuthenticated) { setCodeResult({ stderr: "请先登录后再运行代码" }); return; }
    setRunningCode(true); setCodeResult(null);
    try {
      const res = await codeAPI.submit(code, undefined, customInput);
      const result = { ...(res.result || res) };
      setCodeResult(result); setRunningCode(false);
      if (result.stderr && result.status !== "completed") {
        setAnalyzing(true);
        try { const analysis = await codeAPI.analyze(code, result.stderr); setCodeResult((prev: any) => ({ ...prev, error_analysis: analysis })); } catch {}
        setAnalyzing(false);
      }
    } catch (e: any) { setCodeResult({ stderr: `运行失败: ${e.message}` }); setRunningCode(false); }
  };

  useEffect(() => { loadUser().then(() => { if (!getToken()) router.push("/login"); }); }, []);
  if (!isAuthenticated) return null;

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* Sidebar + Chat — unchanged */}
      <aside className="w-72 glass border-r border-white/[0.06] flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-white/[0.06]">
          <button onClick={newSession} className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl text-sm font-medium hover:from-indigo-500 hover:to-violet-500 transition-all shadow-lg shadow-indigo-500/15"><PlusIcon /> 新对话</button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {sortedSessions.map((s) => (
            <div key={s.id} className={`group flex items-center rounded-xl transition-all relative ${activeSession === s.id ? "bg-indigo-500/10" : "hover:bg-white/[0.04]"}`}>
              <button onClick={() => { setMenuSession(null); loadSession(s.id); }} className="flex-1 text-left px-3 py-2.5 text-sm truncate text-slate-400">{s.title || "未命名"}</button>
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-white/[0.06]">
          <p className="text-sm text-slate-300">{user?.display_name}</p>
          <p className="text-xs text-slate-500">{user?.role === "admin" ? "管理员" : user?.role === "instructor" ? "教师" : "学员"}</p>
        </div>
      </aside>

      <div className="flex-1 flex flex-col bg-gradient-to-b from-[#06060f] to-[#0a0a18]">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <span className="text-3xl">🐍</span>
              <h2 className="text-2xl font-bold text-white mb-2">欢迎来到 PyTutor</h2>
              <p className="text-slate-400 mb-8">你的 AI Python 编程导师。</p>
              <div className="flex gap-3 justify-center flex-wrap">
                {["什么是 Python 列表？", "for 循环怎么用？", "帮我写一个函数", "解释什么是变量"].map((q) => (
                  <button key={q} onClick={() => setInput(q)} className="px-4 py-2 glass border-white/[0.08] rounded-full text-sm text-slate-300 hover:border-indigo-500/30">{q}</button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="max-w-3xl mx-auto space-y-5">
              {messages.map((msg, i) => <ChatMessage key={i} role={msg.role} content={msg.content} hint_level={msg.hint_level} related_concepts={msg.related_concepts} onRunInEditor={(codeStr: string) => { setCode(codeStr); setShowCode(true); setEditorKey(k => k + 1); }} />)}
              {sending && <div className="flex gap-3"><div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold">AI</div><div className="glass border-white/[0.06] rounded-xl px-4 py-3"><div className="flex gap-1.5"><span className="w-2 h-2 bg-slate-500 rounded-full animate-dot-pulse" /><span className="w-2 h-2 bg-slate-500 rounded-full animate-dot-pulse delay-200" /><span className="w-2 h-2 bg-slate-500 rounded-full animate-dot-pulse delay-400" /></div></div></div>}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
        <div className="border-t border-white/[0.06] glass p-4">
          <div className="max-w-3xl mx-auto flex gap-3">
            <button onClick={() => setShowCode(!showCode)} className="flex items-center gap-1.5 px-4 rounded-xl border transition-all flex-shrink-0 text-sm font-medium text-slate-400 hover:text-indigo-400 hover:border-indigo-500/30"><CodeIcon /> 编辑器</button>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }} placeholder="输入你的 Python 问题... (Enter 发送)" rows={1} className="neon w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 resize-none outline-none" style={{ minHeight: "44px", maxHeight: "120px" }} />
            <button onClick={sendMessage} disabled={sending || !input.trim()} className="glow-hover flex items-center px-6 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl text-sm font-medium disabled:opacity-30 transition-all">发送</button>
          </div>
        </div>
      </div>

      {showCode && (
        <aside className="w-[420px] border-l border-white/[0.06] bg-[#0a0a14] flex flex-col animate-slide-in flex-shrink-0">
          <div className="shrink-0 px-5 py-3 border-b border-white/[0.06] flex items-center justify-between">
            <span className="text-sm font-medium text-slate-300">Python 编辑器</span>
            <button onClick={runCode} disabled={runningCode} className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-1.5 rounded-lg text-xs font-medium">{runningCode ? "..." : "▶"} 运行</button>
          </div>
          <div className="flex-1 min-h-0">
            <Editor key={editorKey} height="100%" defaultLanguage="python" theme="vs-dark" value={code} onChange={(v) => setCode(v || "")} options={{ fontSize: 14, fontFamily: "var(--font-geist-mono), monospace", minimap: { enabled: false }, scrollBeyondLastLine: false, lineNumbers: "on", padding: { top: 12 }, automaticLayout: true }} />
          </div>
          <div className="border-t border-white/[0.06] px-3 py-2"><input value={customInput} onChange={(e) => setCustomInput(e.target.value)} placeholder="stdin（如果代码用 input()）" className="w-full bg-black/40 border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-green-300 font-mono outline-none" /></div>
          <div className="flex-1 overflow-y-auto p-4"><p className="text-[10px] text-slate-500 mb-2">运行结果</p>{codeResult && <pre className="text-sm text-emerald-300 font-mono">{codeResult.stdout || codeResult.stderr || "(无输出)"}</pre>}</div>
        </aside>
      )}
    </div>
  );
}

function PlusIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>; }
function CodeIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>; }
