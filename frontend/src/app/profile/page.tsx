"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { profileAPI } from "@/lib/api";

export default function ProfilePage() {
  const { user, loadUser } = useAuthStore();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { loadData(); }, []);
  const loadData = async () => { try { setProfile(await profileAPI.get()); } catch {} finally { setLoading(false); } };

  if (loading) return <div className="flex items-center justify-center h-full"><div className="flex gap-1.5"><span className="w-2 h-2 bg-indigo-400 rounded-full animate-dot-pulse" /><span className="w-2 h-2 bg-indigo-400 rounded-full animate-dot-pulse delay-200" /><span className="w-2 h-2 bg-indigo-400 rounded-full animate-dot-pulse delay-400" /></div></div>;
  if (!profile) return <div className="flex items-center justify-center h-full text-slate-500">无法加载画像</div>;

  const { stats, weaknesses, recommendation } = profile;

  return (
    <div className="h-[calc(100vh-56px)] overflow-y-auto">
      <div className="max-w-5xl mx-auto p-8 space-y-8">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-2xl font-bold shadow-xl shadow-indigo-500/25">{user?.display_name?.[0] || "U"}</div>
          <div><h1 className="text-2xl font-bold text-white">{user?.display_name} 的学习画像</h1><p className="text-slate-400">Level {profile.level} · Python Learner</p></div>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <StatCard label="当前等级" value={`Lv.${profile.level}`} color="from-indigo-500 to-violet-500" />
          <StatCard label="练习完成" value={stats.exercises_completed} color="from-emerald-500 to-teal-500" />
          <StatCard label="通过率" value={`${stats.pass_rate}%`} color="from-amber-500 to-orange-500" />
          <StatCard label="使用提示" value={stats.hints_used} color="from-sky-500 to-cyan-500" />
        </div>

        {recommendation && (
          <div className="glass rounded-2xl p-6 border border-white/[0.06] bg-gradient-to-r from-indigo-500/5 to-violet-500/5">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-2xl">{recommendation.action === "review" ? "🔄" : recommendation.action === "learn" ? "📖" : "🚀"}</div>
              <div className="flex-1">
                <span className={`inline-block text-xs px-2.5 py-1 rounded-full font-medium mb-2 ${recommendation.action === "review" ? "bg-amber-500/10 text-amber-400" : recommendation.action === "learn" ? "bg-indigo-500/10 text-indigo-400" : "bg-emerald-500/10 text-emerald-400"}`}>{recommendation.action === "review" ? "需要复习" : recommendation.action === "learn" ? "推荐学习" : "进阶挑战"}</span>
                <h3 className="text-lg font-bold text-white">{recommendation.concept}</h3>
                <p className="text-sm text-slate-400 mt-1">{recommendation.reason}</p>
              </div>
            </div>
          </div>
        )}

        <div className="glass rounded-2xl border border-white/[0.06] overflow-hidden">
          <div className="px-6 py-4 border-b border-white/[0.06]"><h2 className="font-bold text-white">薄弱知识点</h2></div>
          <div className="p-6">
            {weaknesses.length === 0 ? (
              <div className="text-center py-8"><span className="text-3xl">🎉</span><p className="text-slate-500 mt-2">暂无薄弱点，继续保持！</p></div>
            ) : (
              <div className="space-y-3">
                {weaknesses.map((w: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-4 bg-rose-500/5 border border-rose-500/10 rounded-xl">
                    <div className="flex items-center gap-3"><span className="w-2 h-2 rounded-full bg-rose-400" /><div><span className="font-medium text-white">{w.concept}</span><span className="text-sm text-slate-400 ml-2">失败 {w.fail_count} 次</span></div></div>
                    <div className="flex items-center gap-2"><div className="flex gap-0.5">{Array.from({ length: 5 }).map((_, j) => <div key={j} className={`w-2 h-4 rounded-sm ${j < w.severity ? "bg-rose-400" : "bg-rose-500/10"}`} />)}</div><span className="text-xs text-slate-500 w-16 text-right">严重度 {w.severity}/5</span></div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: any; color: string }) {
  return (
    <div className={`glass rounded-2xl p-5 border border-white/[0.06] hover:border-white/[0.1] transition-all`}>
      <p className="text-3xl font-bold bg-gradient-to-r bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(to right, var(--tw-gradient-stops))` }}><span className={`bg-gradient-to-r ${color} bg-clip-text text-transparent`}>{value}</span></p>
      <p className="text-sm text-slate-500 mt-1">{label}</p>
    </div>
  );
}
