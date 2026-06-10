"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth";
import Link from "next/link";

export function NavAdminLink() {
  const { user, loadUser } = useAuthStore();
  const [show, setShow] = useState(false);

  useEffect(() => { loadUser(); }, []);
  useEffect(() => {
    if (user && (user.role === "admin" || user.role === "instructor")) {
      setShow(true);
    }
  }, [user]);

  if (!show) return null;

  return (
    <Link href="/admin"
      className="relative px-3 py-1.5 text-sm font-medium text-slate-400 hover:text-white transition-colors group">
      管理
      <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-gradient-to-r from-indigo-400 to-violet-400 rounded-full group-hover:w-2/3 transition-all duration-300" />
    </Link>
  );
}
