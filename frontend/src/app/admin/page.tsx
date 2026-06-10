"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { getToken } from "@/lib/api";

const API = "http://localhost:8000/api/v1";
async function fetchAdmin(path: string) {
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error("Permission denied");
  return res.json();
}

export default function AdminPage() {
  const { user, loadUser } = useAuthStore();
  const [tab, setTab] = useState("stats");
  const [stats, setStats] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [exercises, setExercises] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => { loadUser(); if (user?.role !== "admin") return; loadTab(); }, [tab, user]);
  const loadTab = async () => {
    try {
      if (tab === "stats") setStats(await fetchAdmin("/admin/stats"));
      if (tab === "users") setUsers(await fetchAdmin(`/admin/users?search=${search}`));
      if (tab === "exercises") setExercises(await fetchAdmin("/admin/exercises?limit=100"));
      if (tab === "logs") setLogs(await fetchAdmin("/admin/logs?limit=100"));
    } catch {}
  };
  const updateUser = async (id: string, body: any) => {
    await fetch(`${API}/admin/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` }, body: JSON.stringify(body) });
    loadTab();
  };
  const togglePublish = async (id: string, pub: boolean) => {
    await fetch(`${API}/admin/exercises/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` }, body: JSON.stringify({ is_published: pub }) });
    loadTab();
  };

  if (user?.role !== "admin" && user?.role !== "instructor") return <div className="p-8 text-slate-500">需要教师或管理员权限</div>;
  const isAdmin = user?.role === "admin";

  const tabs = [
    ...(isAdmin ? [{ key: "stats", label: "概览" }] : []),
    { key: "exercises", label: "题库管理" },
    ...(isAdmin ? [{ key: "users", label: "用户管理" }, { key: "logs", label: "系统日志" }] : []),
  ];
  // 教师默认打开题库
  if (!isAdmin && tab === "stats") setTab("exercises");

  return (
    <div className="h-[calc(100vh-56px)] flex">
      <aside className="w-48 glass border-r border-white/[0.06] p-3 space-y-1">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${tab === t.key ? "bg-indigo-500/10 text-indigo-300 font-medium" : "text-slate-400 hover:bg-white/[0.04]"}`}>{t.label}</button>
        ))}
      </aside>
      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="text-xl font-bold text-white mb-6">Admin Console</h1>

        {tab === "stats" && stats && (
          <div className="grid grid-cols-4 gap-4">
            {Object.entries(stats).map(([k, v]) => (
              <div key={k} className="glass rounded-xl border border-white/[0.06] p-5">
                <p className="text-3xl font-bold text-indigo-400">{String(v)}</p>
                <p className="text-sm text-slate-500 mt-1">{k}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "users" && (
          <div>
            <input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && loadTab()}
              placeholder="搜索邮箱或名称..." className="neon bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 mb-4 w-64 outline-none" />
            <div className="glass rounded-xl border border-white/[0.06] overflow-hidden">
              <table className="w-full text-sm"><thead className="bg-white/[0.02]"><tr><th className="text-left px-4 py-2 text-slate-400">名称</th><th className="text-left px-4 py-2 text-slate-400">邮箱</th><th className="text-left px-4 py-2 text-slate-400">角色</th><th className="text-left px-4 py-2 text-slate-400">状态</th><th className="text-left px-4 py-2 text-slate-400">操作</th></tr></thead>
                <tbody>{users.map((u: any) => (
                  <tr key={u.id} className="border-t border-white/[0.04]">
                    <td className="px-4 py-2 text-slate-200">{u.display_name}</td><td className="px-4 py-2 text-slate-400">{u.email}</td>
                    <td className="px-4 py-2"><select value={u.role} onChange={(e) => updateUser(u.id, { role: e.target.value })} className="bg-white/[0.04] border border-white/[0.08] rounded px-2 py-0.5 text-xs text-slate-300"><option value="student">student</option><option value="instructor">instructor</option><option value="admin">admin</option></select></td>
                    <td className="px-4 py-2"><span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>{u.is_active ? "正常" : "禁用"}</span></td>
                    <td className="px-4 py-2"><button onClick={() => updateUser(u.id, { is_active: !u.is_active })} className="text-xs text-indigo-400 hover:text-indigo-300">{u.is_active ? "禁用" : "启用"}</button></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}

        {!isAdmin && tab === "exercises" && (
          <div className="mb-6 p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
            <p className="text-sm text-indigo-300 font-medium mb-1">👩‍🏫 教师模式</p>
            <p className="text-xs text-slate-400">你可以管理题库（发布/下架题目、查看使用数据）。学生管理功能需管理员权限。</p>
          </div>
        )}
        {tab === "exercises" && (
          <div className="glass rounded-xl border border-white/[0.06] overflow-hidden">
            <table className="w-full text-sm"><thead className="bg-white/[0.02]"><tr><th className="text-left px-4 py-2 text-slate-400">标题</th><th className="text-left px-4 py-2 text-slate-400">难度</th><th className="text-left px-4 py-2 text-slate-400">知识点</th><th className="text-left px-4 py-2 text-slate-400">来源</th><th className="text-left px-4 py-2 text-slate-400">使用/通过率</th><th className="text-left px-4 py-2 text-slate-400">操作</th></tr></thead>
            <tbody>{exercises.map((e: any) => (
              <tr key={e.id} className="border-t border-white/[0.04]"><td className="px-4 py-2 text-slate-200">{e.title}</td><td className="px-4 py-2 text-slate-400">{"★".repeat(e.difficulty)}</td><td className="px-4 py-2 text-xs text-slate-500">{e.concepts}</td><td className="px-4 py-2 text-xs text-slate-500">{e.source}</td><td className="px-4 py-2 text-xs text-slate-500">{e.use_count}次 / {e.pass_rate ?? "-"}</td><td className="px-4 py-2"><button onClick={() => togglePublish(e.id, !e.is_published)} className="text-xs text-indigo-400 hover:text-indigo-300">{e.is_published ? "下架" : "发布"}</button></td></tr>
            ))}</tbody></table>
          </div>
        )}

        {tab === "logs" && (
          <div className="space-y-2">{logs.map((l: any) => (
            <div key={l.id} className="glass rounded-lg border border-white/[0.04] px-4 py-3 text-sm">
              <span className="font-mono text-xs text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded mr-2">{l.event_type}</span>
              <span className="text-slate-400">{l.concept || ""}</span>
              <span className="text-slate-600 ml-4 text-xs">{l.created_at}</span>
            </div>
          ))}</div>
        )}
      </div>
    </div>
  );
}
