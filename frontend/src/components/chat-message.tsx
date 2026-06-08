"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

const hintLabels: Record<number, { label: string; color: string }> = {
  1: { label: "概念提示", color: "text-emerald-400" },
  2: { label: "思路引导", color: "text-blue-400" },
  3: { label: "指出位置", color: "text-amber-400" },
  4: { label: "部分修正", color: "text-orange-400" },
  5: { label: "完整答案", color: "text-rose-400" },
};

function normalizeContent(content: string): string {
  if (content.startsWith("{") && content.includes('"message"')) {
    try { const p = JSON.parse(content); return p.message || content; }
    catch { return content; }
  }
  return content;
}

interface Props {
  role: "user" | "assistant";
  content: string;
  hint_level?: number;
  related_concepts?: string[];
  userAvatar?: string;
  onRunInEditor?: (code: string) => void;
}

export function ChatMessage({ role, content, hint_level, related_concepts, userAvatar, onRunInEditor }: Props) {
  const isUser = role === "user";
  const displayContent = isUser ? content : normalizeContent(content);

  return (
    <div className={`flex gap-3 animate-fade-in ${isUser ? "flex-row-reverse" : ""}`}>
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold
        ${isUser
          ? "bg-gradient-to-br from-indigo-500 to-violet-600 text-white"
          : "bg-gradient-to-br from-emerald-500 to-teal-600 text-white"}`}>
        {isUser ? (userAvatar || "...") : "AI"}
      </div>

      <div className={`max-w-[78%] ${isUser ? "items-end" : "items-start"}`}>
        {!isUser && hint_level && hintLabels[hint_level] && (
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium mb-2 bg-white/[0.04] border border-white/[0.06] ${hintLabels[hint_level].color}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
            {hintLabels[hint_level].label}
          </div>
        )}

        <div className={`rounded-xl text-sm leading-relaxed overflow-hidden
          ${isUser
            ? "bg-gradient-to-br from-indigo-600/80 to-violet-600/80 text-white px-4 py-2.5"
            : "glass border-white/[0.06] px-0.5 py-0.5"}`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{displayContent}</p>
          ) : (
            <div className="p-4 prose-dark max-w-none">
              <ReactMarkdown
                components={{
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    const codeString = String(children).replace(/\n$/, "");
                    if (!match) return <code className="bg-amber-500/10 text-amber-300 px-1.5 py-0.5 rounded text-[13px] font-mono">{children}</code>;
                    return <CodeBlock language={match[1]} code={codeString} onRunInEditor={onRunInEditor} />;
                  },
                  pre({ children }) { return <>{children}</>; },
                  h1({ children }) { return <h1 className="text-lg font-bold text-white mt-4 mb-2 first:mt-0">{children}</h1>; },
                  h2({ children }) { return <h2 className="text-base font-semibold text-slate-100 mt-3 mb-1.5 first:mt-0">{children}</h2>; },
                  h3({ children }) { return <h3 className="text-sm font-semibold text-slate-200 mt-2 mb-1">{children}</h3>; },
                  p({ children }) { return <p className="mb-2 last:mb-0 leading-[1.7] text-slate-300">{children}</p>; },
                  ul({ children }) { return <ul className="list-disc pl-5 mb-2 space-y-0.5 text-slate-300">{children}</ul>; },
                  ol({ children }) { return <ol className="list-decimal pl-5 mb-2 space-y-0.5 text-slate-300">{children}</ol>; },
                  li({ children }) { return <li className="leading-relaxed">{children}</li>; },
                  strong({ children }) { return <strong className="font-semibold text-white">{children}</strong>; },
                  blockquote({ children }) { return <blockquote className="border-l-2 border-indigo-500/40 pl-3 italic text-slate-400 my-2">{children}</blockquote>; },
                  a({ children, href }) { return <a href={href} target="_blank" rel="noopener" className="text-indigo-400 underline hover:text-indigo-300">{children}</a>; },
                }}>
                {displayContent}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && related_concepts && related_concepts.length > 0 && (
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {related_concepts.map((c) => (
              <span key={c} className="text-[10px] bg-white/[0.04] border border-white/[0.06] text-slate-400 px-2.5 py-1 rounded-full hover:border-indigo-500/30 hover:text-indigo-300 transition-colors cursor-default">{c}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CodeBlock({ language, code, onRunInEditor }: { language: string; code: string; onRunInEditor?: (code: string) => void }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-white/[0.06]">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900 text-slate-400 text-xs gap-2">
        <span className="flex-shrink-0">{language || "code"}</span>
        <div className="flex items-center gap-1">
          {onRunInEditor && (
            <button onClick={() => onRunInEditor(code)}
              className="flex items-center gap-1 px-2 py-1 rounded hover:bg-emerald-500/10 transition-colors text-emerald-400 hover:text-emerald-300 text-xs">
              ▶ 在编辑器中运行
            </button>
          )}
          <button onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-white/[0.06] transition-colors text-slate-500 hover:text-slate-300">
            {copied ? "已复制" : "复制"}
          </button>
        </div>
      </div>
      <SyntaxHighlighter language={language || "python"} style={oneDark}
        customStyle={{ margin: 0, padding: "14px 18px", fontSize: "13px", borderRadius: 0, background: "#0f172a" }}>
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
