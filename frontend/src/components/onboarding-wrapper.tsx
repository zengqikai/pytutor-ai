"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { OnboardingModal } from "@/components/onboarding-modal";
import { LessonPlayer } from "@/components/lesson-player";
import { DiagnosticFlow } from "@/components/diagnostic-flow";

export function OnboardingWrapper({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore();
  const router = useRouter();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  const [showDiagnostic, setShowDiagnostic] = useState(false);
  const [tutorialStartLesson, setTutorialStartLesson] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!isAuthenticated) {
      setShowOnboarding(false); setShowTutorial(false); setShowDiagnostic(false);
      return;
    }

    // 用用户 ID 而不是 token 前缀：所有 JWT 的头部都是相同的，
    // 按 token.slice(0,16) 会让同一个浏览器里的所有账号共用一个标记。
    const uid = user?.id || user?.email;
    if (!uid) return;

    const done = localStorage.getItem(`onboarding_${uid}`);
    if (done) return;

    if (user?.role && user.role !== "student") return;

    setShowOnboarding(true);
  }, [isAuthenticated, user?.id, user?.role]);

  const handleOnboardingComplete = (level: string) => {
    setShowOnboarding(false);
    // 与读取时用同一个 key，否则"引导已完成"永远写不回去。
    const uid = user?.id || user?.email;
    if (uid) localStorage.setItem(`onboarding_${uid}`, "1");
    switch (level) {
      case "A": setShowTutorial(true); break;
      case "B": setShowDiagnostic(true); break;
      case "C": router.push("/exercises"); break;
      // D = 留在 AI 对话页，不做任何跳转（主动选择自由提问）
      case "D": break;
    }
  };

  return (
    <>
      {showOnboarding && <OnboardingModal onComplete={handleOnboardingComplete} />}
      {showDiagnostic && (
        <DiagnosticFlow onComplete={(result) => {
          setShowDiagnostic(false);
          if (!result.skipped && result.level !== "solid") {
            setTutorialStartLesson("lesson_1");
            setShowTutorial(true);
          } else if (!result.skipped) {
            router.push("/exercises");
          }
        }} />
      )}
      {showTutorial && (
        <LessonPlayer userId={user?.id || "anon"} startLessonId={tutorialStartLesson}
          onComplete={() => setShowTutorial(false)} />
      )}
      {children}

      {isAuthenticated && user?.role === "student" && !showOnboarding && !showTutorial && !showDiagnostic && (
        <button onClick={() => setShowOnboarding(true)}
          className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 text-white flex items-center justify-center shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 hover:scale-110 transition-all group" title="调整学习基础">
          <span className="text-xl">🎓</span>
        </button>
      )}
    </>
  );
}
