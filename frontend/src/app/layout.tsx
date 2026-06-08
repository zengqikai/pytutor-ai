import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { NavUser } from "@/components/nav-user";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PyTutor - AI 编程导师",
  description: "个性化 Python 编程学习 AI 智能导师",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="h-full flex flex-col bg-slate-50">
        <header className="h-14 bg-white/80 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-50">
          <div className="h-full max-w-[1600px] mx-auto px-6 flex items-center gap-1">
            <Link href="/" className="flex items-center gap-2.5 mr-6">
              <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm">Py</span>
              <span className="font-bold text-slate-800 text-base tracking-tight">PyTutor</span>
            </Link>
            <NavLink href="/" icon="💬" label="AI 对话" />
            <NavLink href="/exercises" icon="📝" label="练习中心" />
            <NavLink href="/profile" icon="📊" label="学习画像" />
            <div className="flex-1" />
            <NavUser />
          </div>
        </header>
        <main className="flex-1 overflow-hidden">{children}</main>
      </body>
    </html>
  );
}

function NavLink({ href, icon, label }: { href: string; icon: string; label: string }) {
  return (
    <Link href={href}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors">
      <span className="text-base">{icon}</span>
      {label}
    </Link>
  );
}
