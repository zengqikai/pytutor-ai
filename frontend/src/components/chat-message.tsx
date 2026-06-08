"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

const hintLabels: Record<number, { label: string; color: string; bg: string }> = {
  1: { label: "概念提示", color: "text-emerald-600", bg: "bg-emerald-50" },
  2: { label: "思路引导", color: "text-blue-600", bg: "bg-blue-50" },
  3: { label: "指出位置", color: "text-amber-600", bg: "bg-amber-50" },
  4: { label: "部分修正", color: "text-orange-600", bg: "bg-orange-50" },
  5: { label: "完整答案", color: "text-rose-600", bg: "bg-rose-50" },
};

interface Props {
  role: "user" | "assistant";
  content: string;
  hint_level?: number;
  related_concepts?: string[];
  userAvatar?: string;
}

// 兼容旧数据：如果 content 是 JSON，提取 message 字段
function normalizeContent(content: string): string {
  if (content.startsWith("{") && content.includes('"message"')) {
    try {
      const parsed = JSON.parse(content);
      return parsed.message || content;
    } catch { return content; }
  }
  return content;
}

export function ChatMessage({ role, content, hint_level, related_concepts, userAvatar }: Props) {
  const isUser = role === "user";
  const displayContent = isUser ? content : normalizeContent(content);

  return (
    <div className={`flex gap-3 animate-fade-in ${isUser ? "flex-row-reverse" : ""}`}>
      {/* 头像 */}
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 text-sm font-bold shadow-sm
        ${isUser
          ? "bg-gradient-to-br from-indigo-500 to-violet-600 text-white"
          : "bg-gradient-to-br from-emerald-400 to-teal-500 text-white"}`}>
        {isUser ? (userAvatar || "我") : "AI"}
      </div>

      {/* 消息体 */}
      <div className={`max-w-[78%] ${isUser ? "items-end" : "items-start"}`}>
        {/* 提示等级 */}
        {!isUser && hint_level && hint_level > 0 && hintLabels[hint_level] && (
          <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium mb-2.5 ${hintLabels[hint_level].bg} ${hintLabels[hint_level].color}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
            {hintLabels[hint_level].label}
          </div>
        )}

        {/* 气泡 */}
        <div className={`rounded-2xl text-sm leading-relaxed overflow-hidden
          ${isUser
            ? "bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-200 px-5 py-3"
            : "bg-white border border-slate-200/60 shadow-sm px-1 py-1"}`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{displayContent}</p>
          ) : (
            <div className="p-4 prose-custom max-w-none">
              <ReactMarkdown
                components={{
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    const codeString = String(children).replace(/\n$/, "");
                    const inline = !match;

                    if (inline) {
                      return <code className="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded text-[13px] font-mono">{children}</code>;
                    }

                    return <CodeBlock language={match[1]} code={codeString} />;
                  },
                  pre({ children }) {
                    return <>{children}</>;
                  },
                  h1({ children }) { return <h1 className="text-lg font-bold text-slate-800 mt-4 mb-2 first:mt-0">{children}</h1>; },
                  h2({ children }) { return <h2 className="text-base font-semibold text-slate-800 mt-3 mb-1.5 first:mt-0">{children}</h2>; },
                  h3({ children }) { return <h3 className="text-sm font-semibold text-slate-700 mt-2 mb-1">{children}</h3>; },
                  p({ children }) { return <p className="mb-2 last:mb-0 leading-[1.7]">{children}</p>; },
                  ul({ children }) { return <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>; },
                  ol({ children }) { return <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>; },
                  li({ children }) { return <li className="leading-relaxed">{children}</li>; },
                  strong({ children }) { return <strong className="font-semibold text-slate-900">{children}</strong>; },
                  blockquote({ children }) { return <blockquote className="border-l-3 border-indigo-300 pl-3 italic text-slate-500 my-2">{children}</blockquote>; },
                  table({ children }) { return <div className="overflow-x-auto my-2"><table className="min-w-full border-collapse text-sm">{children}</table></div>; },
                  th({ children }) { return <th className="bg-slate-50 px-3 py-1.5 text-left font-medium border">{children}</th>; },
                  td({ children }) { return <td className="px-3 py-1.5 border">{children}</td>; },
                  a({ children, href }) { return <a href={href} target="_blank" rel="noopener" className="text-indigo-600 underline hover:text-indigo-800">{children}</a>; },
                }}>
                {displayContent}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* 知识点标签 */}
        {!isUser && related_concepts && related_concepts.length > 0 && (
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {related_concepts.map((c) => (
              <span key={c} className="text-[11px] bg-slate-100 text-slate-500 px-2.5 py-1 rounded-full font-medium hover:bg-indigo-50 hover:text-indigo-600 transition-colors cursor-default">
                {c}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800 text-slate-300 text-xs">
        <span className="font-medium">{language || "code"}</span>
        <button onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 rounded-md hover:bg-white/10 transition-colors text-slate-400 hover:text-white">
          {copied ? "✓ 已复制" : "📋 复制"}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "python"}
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: "16px 20px",
          fontSize: "13px",
          borderRadius: 0,
          background: "#1e293b",
        }}>
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
