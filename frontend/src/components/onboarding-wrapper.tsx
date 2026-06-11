"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { OnboardingModal } from "@/components/onboarding-modal";
import { Lesson0 } from "@/components/lesson-0";

export function OnboardingWrapper({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showLesson0, setShowLesson0] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return; }
    // Always check when auth state changes
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
      // Response is wrapped: { data: {...}, message: ..., error: ... }
      const profile = resp.data || resp;

      if (!profile.onboarding_done) {
        setShowOnboarding(true);
      }
    } catch (e) {
      // If profile check fails, still show onboarding (safe default)
      console.warn("Onboarding check failed, showing modal as fallback", e);
      setShowOnboarding(true);
    } finally {
      setLoading(false);
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

  if (loading) return <>{children}</>;

  return (
    <>
      {showOnboarding && <OnboardingModal onComplete={handleOnboardingComplete} />}
      {showLesson0 && <Lesson0 onComplete={handleLesson0Complete} />}
      {children}
    </>
  );
}
