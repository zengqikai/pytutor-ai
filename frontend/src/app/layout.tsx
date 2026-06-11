import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { NavLink } from "@/components/nav-link";
import { NavAdminLink } from "@/components/nav-admin-link";
import { NavUser } from "@/components/nav-user";
import { OnboardingWrapper } from "@/components/onboarding-wrapper";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PyTutor — AI Python 编程导师",
  description: "个性化 AI Python 编程学习平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="h-full flex flex-col bg-[#06060f]">
        {/* 背景光晕 */}
        <div className="fixed inset-0 pointer-events-none z-0">
          <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-indigo-500/8 blur-[120px]" />
          <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-violet-500/6 blur-[100px]" />
        </div>

        {/* Glass Navbar */}
        <header className="sticky top-0 z-50 glass-strong border-b border-white/[0.06]">
          <div className="max-w-[1600px] mx-auto px-6 h-14 flex items-center gap-1">
            <Link href="/" className="flex items-center gap-2.5 mr-8 group">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-shadow">
                Py
              </div>
              <span className="font-bold text-base tracking-tight bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                PyTutor
              </span>
            </Link>
            <NavLink href="/" label="AI 对话" />
            <NavLink href="/exercises" label="练习中心" />
            <NavLink href="/profile" label="学习画像" />
            <NavLink href="/teacher" label="教学分析" />
            <NavAdminLink />
            <div className="flex-1" />
            <NavUser />
          </div>
        </header>

        <main className="flex-1 overflow-hidden relative z-10">
          <OnboardingWrapper>{children}</OnboardingWrapper>
        </main>
      </body>
    </html>
  );
}

