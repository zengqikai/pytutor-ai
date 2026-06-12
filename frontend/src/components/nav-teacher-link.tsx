"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";

export function NavTeacherLink() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const role = user?.role;

  // 只有教师和管理员可见
  if (role !== "instructor" && role !== "admin" && role !== "ADMIN" && role !== "INSTRUCTOR") return null;

  const isActive = pathname === "/teacher" || pathname.startsWith("/teacher");
  return (
    <Link href="/teacher"
      className={`relative px-3 py-1.5 text-sm font-medium transition-colors group
        ${isActive ? "text-white" : "text-slate-400 hover:text-white"}`}>
      教学分析
      <span className={`absolute bottom-0 left-1/2 -translate-x-1/2 h-[2px] bg-gradient-to-r from-indigo-400 to-violet-400 rounded-full transition-all duration-300
        ${isActive ? "w-2/3" : "w-0 group-hover:w-2/3"}`} />
    </Link>
  );
}
