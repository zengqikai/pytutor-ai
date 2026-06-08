"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { getToken } from "@/lib/api";

const API = "http://localhost:8000/api/v1";

async function fetchAdmin(path: string) {
  const res = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("权限不足");
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
    await fetch(`${API}/admin/users/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
      body: JSON.stringify(body),
    });
    loadTab();
  };

  const togglePublish = async (id: string, pub: boolean) => {
    await fetch(`${API}/admin/exercises/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
      body: JSON.stringify({ is_published: pub }),
    });
    loadTab();
  };

  if (user?.role !== "admin") return <div className="p-8 text-gray-400">需要管理员权限</div>;

  const tabs = [
    { key: "stats", label: "概览" },
    { key: "users", label: "用户" },
    { key: "exercises", label: "题库" },
    { key: "logs", label: "日志" },
  ];

  return (
    <div className="h-[calc(100vh-56px)] flex">
      <aside className="w-48 bg-white border-r p-3 space-y-1">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${tab === t.key ? "bg-indigo-50 text-indigo-700 font-medium" : "text-slate-600 hover:bg-slate-50"}`}>
            {t.label}
          </button>
        ))}
      </aside>
      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="text-xl font-bold mb-6">管理员控制台</h1>

        {tab === "stats" && stats && (
          <div className="grid grid-cols-4 gap-4">
            {Object.entries(stats).map(([k, v]) => (
              <div key={k} className="bg-white rounded-xl border p-5">
                <p className="text-3xl font-bold text-indigo-600">{String(v)}</p>
                <p className="text-sm text-slate-500 mt-1">{k}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "users" && (
          <div>
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadTab()}
              placeholder="搜索邮箱或名称..." className="border rounded-lg px-3 py-2 text-sm mb-4 w-64" />
            <div className="bg-white rounded-xl border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50"><tr>
                  <th className="text-left px-4 py-2">名称</th><th className="text-left px-4 py-2">邮箱</th>
                  <th className="text-left px-4 py-2">角色</th><th className="text-left px-4 py-2">状态</th>
                  <th className="text-left px-4 py-2">操作</th>
                </tr></thead>
                <tbody>
                  {users.map((u: any) => (
                    <tr key={u.id} className="border-t">
                      <td className="px-4 py-2">{u.display_name}</td>
                      <td className="px-4 py-2 text-slate-500">{u.email}</td>
                      <td className="px-4 py-2">
                        <select value={u.role} onChange={(e) => updateUser(u.id, { role: e.target.value })}
                          className="border rounded px-2 py-0.5 text-xs">
                          <option value="student">student</option>
                          <option value="instructor">instructor</option>
                          <option value="admin">admin</option>
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                          {u.is_active ? "正常" : "禁用"}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <button onClick={() => updateUser(u.id, { is_active: !u.is_active })}
                          className="text-xs text-indigo-600 hover:underline">
                          {u.is_active ? "禁用" : "启用"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "exercises" && (
          <div className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50"><tr>
                <th className="text-left px-4 py-2">标题</th><th className="text-left px-4 py-2">难度</th>
                <th className="text-left px-4 py-2">知识点</th><th className="text-left px-4 py-2">来源</th>
                <th className="text-left px-4 py-2">使用/通过率</th><th className="text-left px-4 py-2">操作</th>
              </tr></thead>
              <tbody>
                {exercises.map((e: any) => (
                  <tr key={e.id} className="border-t">
                    <td className="px-4 py-2">{e.title}</td>
                    <td className="px-4 py-2">{"★".repeat(e.difficulty)}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">{e.concepts}</td>
                    <td className="px-4 py-2 text-xs">{e.source}</td>
                    <td className="px-4 py-2 text-xs">{e.use_count}次 / {e.pass_rate ?? "-"}</td>
                    <td className="px-4 py-2">
                      <button onClick={() => togglePublish(e.id, !e.is_published)}
                        className="text-xs text-indigo-600 hover:underline">
                        {e.is_published ? "下架" : "发布"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "logs" && (
          <div className="space-y-2">
            {logs.map((l: any) => (
              <div key={l.id} className="bg-white rounded-lg border px-4 py-3 text-sm">
                <span className="font-mono text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded mr-2">{l.event_type}</span>
                <span className="text-slate-500">{l.concept || ""}</span>
                <span className="text-slate-400 ml-4 text-xs">{l.created_at}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
