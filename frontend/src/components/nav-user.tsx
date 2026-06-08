"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

export function NavUser() {
  const router = useRouter();
  const { user, isAuthenticated, loadUser, logout } = useAuthStore();
  const [showMenu, setShowMenu] = useState(false);

  useEffect(() => { loadUser(); }, []);

  if (!isAuthenticated || !user) {
    return (
      <div className="flex gap-2">
        <button onClick={() => router.push("/login")}
          className="px-4 py-1.5 text-sm font-medium text-slate-400 hover:text-white transition-colors">登录</button>
        <button onClick={() => router.push("/register")}
          className="px-4 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors">注册</button>
      </div>
    );
  }

  return (
    <div className="relative">
      <button onClick={() => setShowMenu(!showMenu)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-white/[0.06] transition-colors">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold">
          {user.display_name?.[0] || "U"}
        </div>
        <span className="text-sm font-medium text-slate-300">{user.display_name}</span>
      </button>
      {showMenu && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full mt-2 w-52 glass rounded-xl border border-white/[0.08] py-1 z-20 animate-fade-in shadow-xl">
            <div className="px-4 py-2.5 border-b border-white/[0.06]">
              <p className="text-sm font-medium text-white">{user.display_name}</p>
              <p className="text-xs text-slate-400 mt-0.5">{user.email}</p>
            </div>
            <button onClick={() => { logout(); router.push("/login"); }}
              className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.04] transition-colors">
              退出登录
            </button>
          </div>
        </>
      )}
    </div>
  );
}
