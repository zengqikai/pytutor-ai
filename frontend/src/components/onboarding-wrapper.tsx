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
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token || !user || user.role !== "student") { setReady(true); return; }

    // 本地优先：localStorage 记录过就不再弹
    const done = localStorage.getItem(`onboarding_${user.id}`);
    if (done) { setReady(true); return; }

    setShowOnboarding(true);
    setReady(true);
  }, [user]);

  const handleOnboardingComplete = (level: string) => {
    setShowOnboarding(false);
    // 记住已完成
    if (user?.id) localStorage.setItem(`onboarding_${user.id}`, "1");
    switch (level) {
      case "A": setShowTutorial(true); break;
      case "B": setShowDiagnostic(true); break;
      case "C": router.push("/exercises"); break;
    }
  };

  if (!ready) return null;

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
