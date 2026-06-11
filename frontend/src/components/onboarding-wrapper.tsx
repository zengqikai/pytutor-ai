"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { OnboardingModal } from "@/components/onboarding-modal";
import { Lesson0 } from "@/components/lesson-0";

export function OnboardingWrapper({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showLesson0, setShowLesson0] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || checked) return;
    checkOnboarding();
  }, [isAuthenticated]);

  const checkOnboarding = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      const r = await fetch("http://localhost:8000/api/v1/profile/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await r.json();
      // Show onboarding if not yet completed (2.0 feature flag)
      if (!data.onboarding_done && !localStorage.getItem("onboarding_skipped")) {
        setShowOnboarding(true);
      }
    } catch {} finally {
      setChecked(true);
    }
  };

  const handleOnboardingComplete = (level: string) => {
    setShowOnboarding(false);
    if (level === "A") {
      setShowLesson0(true);
    }
  };

  const handleLesson0Complete = () => {
    setShowLesson0(false);
  };

  return (
    <>
      {showOnboarding && <OnboardingModal onComplete={handleOnboardingComplete} />}
      {showLesson0 && <Lesson0 onComplete={handleLesson0Complete} />}
      {children}
    </>
  );
}
