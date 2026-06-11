"use client";

import { useState, useEffect } from "react";
import { API_BASE_URL } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

export default function TeacherPage() {
  const { isAuthenticated, loadUser } = useAuthStore();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadUser(); }, []);
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchData();
  }, [isAuthenticated]);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      const r = await fetch(`${API_BASE_URL}/teacher/overview`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(await r.json());
    } catch {} finally { setLoading(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-full"><div className="flex gap-1.5"><span className="w-2 h-2 bg-indigo-400 rounded-full animate-dot-pulse" /><span className="w-2 h-2 bg-indigo-400 rounded-full animate-dot-pulse delay-200" /><span className="w-2 h-2 bg-indigo-400 rounded-full animate-dot-pulse delay-400" /></div></div>;
  if (!data) return <div className="flex items-center justify-center h-full text-slate-500">无法加载数据</div>;

  const { summary, misconception_stats, weak_topic_stats, students, recent_events } = data;
  const maxMc = Math.max(1, ...misconception_stats.map((m: any) => m.count));

  return (
    <div className="h-[calc(100vh-56px)] overflow-y-auto">
      <div className="max-w-6xl mx-auto p-8 space-y-6">
        <h1 className="text-2xl font-bold text-white">📊 教学效果分析</h1>

        {/* Summary Cards */}
        <div className="grid grid-cols-5 gap-4">
          <StatCard label="学生总数" value={summary.total_students} color="from-indigo-500 to-violet-500" />
          <StatCard label="平均等级" value={`Lv.${summary.avg_level}`} color="from-emerald-500 to-teal-500" />
          <StatCard label="练习通过" value={summary.total_passed} color="from-amber-500 to-orange-500" />
          <StatCard label="通过率" value={`${summary.pass_rate}%`} color="from-sky-500 to-cyan-500" />
          <StatCard label="总提交" value={summary.total_completed} color="from-rose-500 to-pink-500" />
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Misconception Frequency */}
          <div className="glass rounded-2xl border border-white/[0.06] p-6">
            <h2 className="font-bold text-white mb-4">🧠 误区出现频次</h2>
            <div className="space-y-2">
              {misconception_stats.map((m: any) => (
                <div key={m.code} className="flex items-center gap-3">
                  <span className="w-12 text-xs font-mono text-slate-400">{m.code}</span>
                  <div className="flex-1 h-5 bg-white/[0.04] rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-rose-500 to-amber-500 rounded-full transition-all flex items-center justify-end pr-2"
                      style={{ width: `${(m.count / maxMc) * 100}%` }}>
                      {m.count > 0 && <span className="text-[10px] text-white font-medium">{m.count}</span>}
                    </div>
                  </div>
                  <span className="w-24 text-xs text-slate-500 truncate">{m.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Weak Topics */}
          <div className="glass rounded-2xl border border-white/[0.06] p-6">
            <h2 className="font-bold text-white mb-4">⚠️ 薄弱知识点 TOP 10</h2>
            {weak_topic_stats.length === 0 ? (
              <p className="text-slate-500 text-sm text-center py-8">暂无数据</p>
            ) : (
              <div className="space-y-2">
                {weak_topic_stats.map((w: any, i: number) => (
                  <div key={w.concept} className="flex items-center gap-3">
                    <span className="text-xs text-slate-500 w-5">{i + 1}</span>
                    <span className="flex-1 text-sm text-slate-300">{w.concept}</span>
                    <span className="text-xs text-amber-400 font-medium">{w.count} 次</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Hint Dependency */}
        <div className="glass rounded-2xl border border-white/[0.06] p-6">
          <h2 className="font-bold text-white mb-4">📖 提示依赖度分布</h2>
          <div className="flex gap-6">
            {[
              { label: "低依赖", count: summary.hint_dependency.low, color: "bg-emerald-500" },
              { label: "中等", count: summary.hint_dependency.medium, color: "bg-amber-500" },
              { label: "高依赖", count: summary.hint_dependency.high, color: "bg-rose-500" },
            ].map((h) => (
              <div key={h.label} className="flex-1 text-center">
                <div className={`w-full h-3 rounded-full ${h.color} opacity-80`} style={{ width: "100%" }}>
                  <div className="h-full bg-white/[0.04] rounded-full" style={{ width: `${100 - (h.count / Math.max(1, summary.total_students) * 100)}%`, marginLeft: "auto" }} />
                </div>
                <p className="text-xs text-slate-400 mt-2">{h.label}: <strong className="text-white">{h.count}</strong> 人</p>
              </div>
            ))}
          </div>
        </div>

        {/* Student List */}
        <div className="glass rounded-2xl border border-white/[0.06] overflow-hidden">
          <div className="px-6 py-4 border-b border-white/[0.06]"><h2 className="font-bold text-white">👨‍🎓 学生列表</h2></div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.04] text-left text-xs text-slate-500 uppercase tracking-wider">
                  <th className="px-6 py-3">学生</th>
                  <th className="px-6 py-3">等级</th>
                  <th className="px-6 py-3">通过/完成</th>
                  <th className="px-6 py-3">提示依赖</th>
                  <th className="px-6 py-3">最近误区</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s: any) => (
                  <tr key={s.email} className="border-b border-white/[0.02] hover:bg-white/[0.02]">
                    <td className="px-6 py-3">
                      <p className="font-medium text-slate-200">{s.name}</p>
                      <p className="text-xs text-slate-500">{s.email}</p>
                    </td>
                    <td className="px-6 py-3"><span className="px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 text-xs">Lv.{s.level}</span></td>
                    <td className="px-6 py-3 text-slate-300">{s.exercises_passed}/{s.exercises_completed}</td>
                    <td className="px-6 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${s.hint_dependency === "high" ? "bg-rose-500/10 text-rose-400" : s.hint_dependency === "medium" ? "bg-amber-500/10 text-amber-400" : "bg-emerald-500/10 text-emerald-400"}`}>
                        {s.hint_dependency === "high" ? "高" : s.hint_dependency === "medium" ? "中" : "低"}
                      </span>
                    </td>
                    <td className="px-6 py-3">
                      <div className="flex gap-1 flex-wrap">
                        {s.recent_misconceptions.map((m: string) => (
                          <span key={m} className="text-[10px] bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded">{m}</span>
                        ))}
                        {s.recent_misconceptions.length === 0 && <span className="text-xs text-slate-600">-</span>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Events */}
        <div className="glass rounded-2xl border border-white/[0.06] overflow-hidden">
          <div className="px-6 py-4 border-b border-white/[0.06]"><h2 className="font-bold text-white">📝 最近学习动态</h2></div>
          <div className="p-4 space-y-1 max-h-60 overflow-y-auto">
            {recent_events.map((e: any, i: number) => (
              <div key={i} className="flex items-center gap-3 text-xs py-1.5 px-3 rounded-lg hover:bg-white/[0.02]">
                <span className="w-20 text-slate-500">{e.time?.slice(11, 19) || ""}</span>
                <span className="w-16 text-slate-400">{e.user}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] ${e.event.includes("passed") ? "bg-emerald-500/10 text-emerald-400" : e.event.includes("failed") ? "bg-rose-500/10 text-rose-400" : "bg-indigo-500/10 text-indigo-400"}`}>{e.event}</span>
                <span className="text-slate-500">{e.concept}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: any; color: string }) {
  return (
    <div className="glass rounded-2xl p-5 border border-white/[0.06] text-center">
      <p className={`text-2xl font-bold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>{value}</p>
      <p className="text-xs text-slate-500 mt-1">{label}</p>
    </div>
  );
}
