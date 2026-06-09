"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

export function NavLink({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  const isActive = pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <Link href={href}
      className={`relative px-3 py-1.5 text-sm font-medium transition-colors group
        ${isActive ? "text-white" : "text-slate-400 hover:text-white"}`}>
      {label}
      <span className={`absolute bottom-0 left-1/2 -translate-x-1/2 h-[2px] bg-gradient-to-r from-indigo-400 to-violet-400 rounded-full transition-all duration-300
        ${isActive ? "w-2/3" : "w-0 group-hover:w-2/3"}`} />
    </Link>
  );
}
