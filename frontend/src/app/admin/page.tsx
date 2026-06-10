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
  const [tab, setTab] = useState("students");
  const [stats, setStats] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [exercises, setExercises] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [students, setStudents] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [selectedStudent, setSelectedStudent] = useState<any>(null);
  const [studentDetail, setStudentDetail] = useState<any>(null);
  const [selectedExercise, setSelectedExercise] = useState<any>(null);
  const [exerciseRecords, setExerciseRecords] = useState<any[]>([]);

  useEffect(() => { loadUser(); }, []);
  useEffect(() => {
    if (user && (user.role === "admin" || user.role === "instructor")) loadTab();
  }, [tab, user]);

  const isAdmin = user?.role === "admin";

  const loadTab = async () => {
    try {
      if (tab === "stats") setStats(await fetchAdmin("/admin/stats"));
      if (tab === "users") setUsers(await fetchAdmin(`/admin/users?search=${search}`));
      if (tab === "exercises") setExercises(await fetchAdmin("/admin/exercises?limit=100"));
      if (tab === "students") {
        const d = await fetchAdmin("/admin/students");
        setStudents(d.students || []);
      }
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

  const viewStudent = async (s: any) => {
    if (selectedStudent?.id === s.id) { setSelectedStudent(null); setStudentDetail(null); return; }
    setSelectedStudent(s);
    try { setStudentDetail(await fetchAdmin(`/admin/students/${s.id}`)); } catch { setStudentDetail(null); }
  };

  const viewExercise = async (e: any) => {
    if (selectedExercise?.id === e.id) { setSelectedExercise(null); setExerciseRecords([]); return; }
    setSelectedExercise(e);
    try { const d = await fetchAdmin(`/admin/exercises/${e.id}/records`); setExerciseRecords(d.records || []); } catch { setExerciseRecords([]); }
  };

  if (user?.role !== "admin" && user?.role !== "instructor") {
    return <div className="p-8 text-slate-500">需要教师或管理员权限</div>;
  }

  const tabs = [
    ...(isAdmin ? [{ key: "stats", label: "系统概览" }] : []),
    { key: "students", label: "学生概览" },
    { key: "exercises", label: "题库管理" },
    ...(isAdmin ? [{ key: "users", label: "用户管理" }, { key: "logs", label: "系统日志" }] : []),
  ];

  return (
    <div className="h-[calc(100vh-56px)] flex">
      <aside className="w-48 glass border-r border-white/[0.06] p-3 space-y-1">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${tab === t.key ? "bg-indigo-500/10 text-indigo-300 font-medium" : "text-slate-400 hover:bg-white/[0.04]"}`}>{t.label}</button>
        ))}
      </aside>
      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="text-xl font-bold text-white mb-6">管理控制台</h1>

        {/* 系统概览 */}
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

        {/* 学生概览 */}
        {tab === "students" && (
          <>
            <div className="glass rounded-xl border border-white/[0.06] overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-white/[0.02]"><tr>
                  <th className="text-left px-4 py-3 text-slate-400">学生</th><th className="text-left px-4 py-3 text-slate-400">邮箱</th>
                  <th className="text-center px-4 py-3 text-slate-400">等级</th>
                  <th className="text-center px-4 py-3 text-slate-400">通过题目</th><th className="text-center px-4 py-3 text-slate-400">提示</th>
                  <th className="text-center px-4 py-3 text-slate-400">状态</th>
                </tr></thead>
                <tbody>
                  {students.map((s: any) => (
                    <tr key={s.id} onClick={() => viewStudent(s)}
                      className={`border-t border-white/[0.04] hover:bg-white/[0.02] cursor-pointer ${selectedStudent?.id === s.id ? "bg-indigo-500/10" : ""}`}>
                      <td className="px-4 py-3 text-slate-200 font-medium">{s.name}</td>
                      <td className="px-4 py-3 text-slate-500 text-xs">{s.email}</td>
                      <td className="px-4 py-3 text-center"><span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400">Lv.{s.level}</span></td>
                      <td className="px-4 py-3 text-center text-emerald-400">{s.exercises_passed}</td>
                      <td className="px-4 py-3 text-center text-amber-400">{s.hints_used}</td>
                      <td className="px-4 py-3 text-center"><span className={`text-xs px-2 py-0.5 rounded-full ${s.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>{s.is_active ? "活跃" : "禁用"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {selectedStudent && studentDetail && (
              <div className="glass rounded-xl border border-white/[0.06] p-6 mt-4 animate-fade-in">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-white">{studentDetail.student?.name} 的学习详情</h3>
                  <button onClick={() => { setSelectedStudent(null); setStudentDetail(null); }} className="text-xs text-slate-500 hover:text-slate-300">关闭</button>
                </div>
                <div className="grid grid-cols-4 gap-3 mb-6">
                  <StatMini label="等级" value={`Lv.${studentDetail.student?.level}`} />
                  <StatMini label="通过题目" value={studentDetail.student?.exercises_passed || 0} />
                  <StatMini label="使用提示" value={studentDetail.student?.hints_used || 0} />
                </div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">练习记录</p>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {studentDetail.events?.map((ev: any, i: number) => (
                    <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${ev.type === "exercise_passed" ? "bg-emerald-500/5 border-emerald-500/10" : "bg-rose-500/5 border-rose-500/10"}`}>
                      <div className="flex items-center gap-3">
                        <span className={ev.type === "exercise_passed" ? "text-emerald-400" : "text-rose-400"}>{ev.type === "exercise_passed" ? "✅" : "❌"}</span>
                        <div><p className="text-sm text-slate-300">{ev.title || ev.concept || "练习"}</p><p className="text-xs text-slate-600">{ev.time}</p></div>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        {ev.score_pct > 0 && <span className={`px-2 py-0.5 rounded-full ${ev.score_pct === 100 ? "bg-emerald-500/10 text-emerald-400" : ev.score_pct >= 50 ? "bg-amber-500/10 text-amber-400" : "bg-slate-500/10 text-slate-400"}`}>{ev.score_pct === 100 ? "⭐独立" : ev.score_pct >= 50 ? "🌟提示" : "📖答案"}</span>}
                        {ev.used_hints > 0 && <span className="text-amber-400 text-xs">提示×{ev.used_hints}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* 题库管理 */}
        {tab === "exercises" && (
          <>
            <div className="glass rounded-xl border border-white/[0.06] overflow-hidden">
              <table className="w-full text-sm"><thead className="bg-white/[0.02]"><tr>
                <th className="text-left px-4 py-2 text-slate-400">标题</th><th className="text-left px-4 py-2 text-slate-400">难度</th>
                <th className="text-left px-4 py-2 text-slate-400">知识点</th><th className="text-left px-4 py-2 text-slate-400">来源</th>
                <th className="text-left px-4 py-2 text-slate-400">使用/通过率</th><th className="text-left px-4 py-2 text-slate-400">操作</th>
              </tr></thead>
              <tbody>{exercises.map((e: any) => (
                <tr key={e.id} onClick={() => viewExercise(e)}
                  className={`border-t border-white/[0.04] hover:bg-white/[0.02] cursor-pointer ${selectedExercise?.id === e.id ? "bg-indigo-500/10" : ""}`}>
                  <td className="px-4 py-2 text-slate-200">{e.title}</td>
                  <td className="px-4 py-2 text-slate-400">{"★".repeat(e.difficulty)}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{e.concepts}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{e.source}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{e.use_count}次 / {e.pass_rate ?? "-"}</td>
                  <td className="px-4 py-2"><button onClick={(ev) => { ev.stopPropagation(); togglePublish(e.id, !e.is_published); }} className="text-xs text-indigo-400 hover:text-indigo-300">{e.is_published ? "下架" : "发布"}</button></td>
                </tr>
              ))}</tbody></table>
            </div>
            {selectedExercise && (
              <div className="glass rounded-xl border border-white/[0.06] p-6 mt-4 animate-fade-in">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-white">{selectedExercise.title} - 提交记录</h3>
                  <button onClick={() => { setSelectedExercise(null); setExerciseRecords([]); }} className="text-xs text-slate-500 hover:text-slate-300">关闭</button>
                </div>
                {exerciseRecords.length === 0 ? (
                  <p className="text-center text-slate-500 text-sm py-4">暂无提交记录</p>
                ) : (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {exerciseRecords.map((r: any, i: number) => (
                      <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${r.passed ? "bg-emerald-500/5 border-emerald-500/10" : "bg-rose-500/5 border-rose-500/10"}`}>
                        <div className="flex items-center gap-3">
                          <span className={r.passed ? "text-emerald-400" : "text-rose-400"}>{r.passed ? "✅" : "❌"}</span>
                          <div><p className="text-sm text-slate-300">{r.student_name} <span className="text-xs text-slate-500">({r.student_email})</span></p><p className="text-xs text-slate-600">{r.time}</p></div>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                          {r.score_pct > 0 && <span className={`px-2 py-0.5 rounded-full ${r.score_pct === 100 ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}>{r.score_pct === 100 ? "⭐独立" : "🌟提示"}</span>}
                          {r.used_hints > 0 && <span className="text-amber-400">提示×{r.used_hints}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* 用户管理 */}
        {tab === "users" && (
          <div>
            <input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && loadTab()}
              placeholder="搜索邮箱或名称..." className="neon bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 mb-4 w-64 outline-none" />
            <div className="glass rounded-xl border border-white/[0.06] overflow-hidden">
              <table className="w-full text-sm"><thead className="bg-white/[0.02]"><tr><th className="text-left px-4 py-2 text-slate-400">名称</th><th className="text-left px-4 py-2 text-slate-400">邮箱</th><th className="text-left px-4 py-2 text-slate-400">角色</th><th className="text-left px-4 py-2 text-slate-400">状态</th><th className="text-left px-4 py-2 text-slate-400">操作</th></tr></thead>
              <tbody>{users.map((u: any) => (
                <tr key={u.id} className="border-t border-white/[0.04]"><td className="px-4 py-2 text-slate-200">{u.display_name}</td><td className="px-4 py-2 text-slate-400">{u.email}</td>
                  <td className="px-4 py-2"><select value={u.role} onChange={(ev) => updateUser(u.id, { role: ev.target.value })} className="bg-white/[0.04] border border-white/[0.08] rounded px-2 py-0.5 text-xs text-slate-300"><option value="student">student</option><option value="instructor">instructor</option><option value="admin">admin</option></select></td>
                  <td className="px-4 py-2"><span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>{u.is_active ? "正常" : "禁用"}</span></td>
                  <td className="px-4 py-2"><button onClick={() => updateUser(u.id, { is_active: !u.is_active })} className="text-xs text-indigo-400 hover:text-indigo-300">{u.is_active ? "禁用" : "启用"}</button></td></tr>
              ))}</tbody></table>
            </div>
          </div>
        )}

        {/* 日志 */}
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

function StatMini({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-white/[0.02] rounded-lg p-3 text-center">
      <p className="text-2xl font-bold text-indigo-400">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
