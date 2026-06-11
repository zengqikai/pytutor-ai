"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { OnboardingModal } from "@/components/onboarding-modal";
import { LessonPlayer } from "@/components/lesson-player";

export function OnboardingWrapper({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return; }
    checkOnboarding();
  }, [isAuthenticated]);

  const checkOnboarding = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("auth_token");
      const r = await fetch("http://localhost:8000/api/v1/profile/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const resp = await r.json();
      const profile = resp.data || resp;
      if (!profile.onboarding_done) {
        setShowOnboarding(true);
      }
    } catch (e) {
      console.warn("Onboarding check failed", e);
    } finally {
      setLoading(false);
    }
  };

  const handleOnboardingComplete = (level: string) => {
    setShowOnboarding(false);
    if (level === "A") {
      setShowTutorial(true);
    }
  };

  if (loading) return <>{children}</>;

  return (
    <>
      {showOnboarding && <OnboardingModal onComplete={handleOnboardingComplete} />}
      {showTutorial && <LessonPlayer onComplete={() => setShowTutorial(false)} />}
      {children}

      {/* 永久入口：右下角浮动按钮 */}
      {isAuthenticated && !showOnboarding && !showTutorial && (
        <button
          onClick={() => {
            const userId = localStorage.getItem("auth_token")?.slice(0, 16) || "anon";
            const saved = localStorage.getItem(`pytutor_progress_${userId}`);
            if (saved) {
              setShowTutorial(true);
            } else {
              setShowOnboarding(true);
            }
          }}
          className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 text-white flex items-center justify-center shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 hover:scale-110 transition-all group"
          title="继续学习"
        >
          <span className="text-xl">🎓</span>
          <span className="absolute right-14 bg-gray-900 text-white text-xs px-2 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            调整学习基础
          </span>
        </button>
      )}
    </>
  );
}
