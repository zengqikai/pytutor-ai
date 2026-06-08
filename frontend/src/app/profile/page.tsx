"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { profileAPI } from "@/lib/api";

export default function ProfilePage() {
  const { user, loadUser } = useAuthStore();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try { setProfile(await profileAPI.get()); } catch {} finally { setLoading(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="flex gap-1.5">
        <span className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse-dot" />
        <span className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse-dot" style={{ animationDelay: "0.2s" }} />
        <span className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse-dot" style={{ animationDelay: "0.4s" }} />
      </div>
    </div>
  );
  if (!profile) return <div className="flex items-center justify-center h-full text-slate-400">无法加载画像</div>;

  const { stats, weaknesses, recommendation } = profile;

  return (
    <div className="h-[calc(100vh-56px)] overflow-y-auto">
      <div className="max-w-5xl mx-auto p-8 space-y-8">
        {/* 头部 */}
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-indigo-200">
            {user?.display_name?.[0] || "U"}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">{user?.display_name} 的学习画像</h1>
            <p className="text-slate-500">等级 {profile.level} · Python 学习者</p>
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard icon="📊" label="当前等级" value={`Lv.${profile.level}`} color="from-indigo-500 to-violet-500" />
          <StatCard icon="✅" label="练习完成" value={stats.exercises_completed} color="from-emerald-500 to-teal-500" />
          <StatCard icon="🎯" label="通过率" value={`${stats.pass_rate}%`} color="from-amber-500 to-orange-500" />
          <StatCard icon="💡" label="使用提示" value={stats.hints_used} color="from-sky-500 to-cyan-500" />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <StatMini label="代码提交" value={stats.code_submissions} />
          <StatMini label="聊天消息" value={stats.chat_messages} />
          <StatMini label="练习通过" value={stats.exercises_passed} />
        </div>

        {/* 推荐卡片 */}
        {recommendation && (
          <div className="bg-gradient-to-r from-indigo-50 to-violet-50 rounded-2xl p-6 border border-indigo-100">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center shadow-sm text-2xl">
                {recommendation.action === "review" ? "🔄" : recommendation.action === "learn" ? "📖" : "🚀"}
              </div>
              <div className="flex-1">
                <span className={`inline-block text-xs px-2.5 py-1 rounded-full font-medium mb-2
                  ${recommendation.action === "review" ? "bg-amber-100 text-amber-700" :
                    recommendation.action === "learn" ? "bg-indigo-100 text-indigo-700" : "bg-emerald-100 text-emerald-700"}`}>
                  {recommendation.action === "review" ? "需要复习" : recommendation.action === "learn" ? "推荐学习" : "进阶挑战"}
                </span>
                <h3 className="text-lg font-bold text-slate-800">{recommendation.concept}</h3>
                <p className="text-sm text-slate-600 mt-1">{recommendation.reason}</p>
              </div>
            </div>
          </div>
        )}

        {/* 薄弱点 */}
        <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h2 className="font-bold text-slate-800">薄弱知识点</h2>
          </div>
          <div className="p-6">
            {weaknesses.length === 0 ? (
              <div className="text-center py-8">
                <span className="text-3xl">🎉</span>
                <p className="text-slate-500 mt-2">暂无薄弱点，继续保持！</p>
              </div>
            ) : (
              <div className="space-y-3">
                {weaknesses.map((w: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-4 bg-rose-50 rounded-xl">
                    <div className="flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-rose-400" />
                      <div>
                        <span className="font-medium text-slate-800">{w.concept}</span>
                        <span className="text-sm text-slate-500 ml-2">失败 {w.fail_count} 次</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex gap-0.5">
                        {Array.from({ length: 5 }).map((_, j) => (
                          <div key={j} className={`w-2 h-4 rounded-sm ${j < w.severity ? "bg-rose-400" : "bg-rose-100"}`} />
                        ))}
                      </div>
                      <span className="text-xs text-slate-500 w-16 text-right">严重度 {w.severity}/5</span>
                    </div>
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

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: any; color: string }) {
  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-200/60 shadow-sm hover:shadow-md transition-shadow">
      <span className="text-2xl">{icon}</span>
      <p className="text-3xl font-bold text-slate-800 mt-3">{value}</p>
      <p className="text-sm text-slate-500 mt-1">{label}</p>
    </div>
  );
}

function StatMini({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-xl p-4 border border-slate-200/60 text-center">
      <p className="text-2xl font-bold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
