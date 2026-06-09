"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface ExerciseState {
  selected: any | null;
  userCode: string;
  customInput: string;
  testResult: any | null;
  result: any | null;
  hintText: string;
  hintLevel: number;
  showSolution: boolean;
  solutionText: string;
  difficulty: number;
  setSelected: (ex: any | null) => void;
  setUserCode: (code: string) => void;
  setCustomInput: (input: string) => void;
  setTestResult: (r: any | null) => void;
  setResult: (r: any | null) => void;
  setHintText: (t: string) => void;
  setHintLevel: (l: number) => void;
  setShowSolution: (v: boolean) => void;
  setSolutionText: (t: string) => void;
  setDifficulty: (d: number) => void;
  reset: () => void;
}

export const useExerciseStore = create<ExerciseState>()(
  persist(
    (set) => ({
      selected: null,
      userCode: "# 在此编写你的代码\n",
      customInput: "",
      testResult: null,
      result: null,
      hintText: "",
      hintLevel: 1,
      showSolution: false,
      solutionText: "",
      difficulty: 2,
      setSelected: (ex) => set({ selected: ex }),
      setUserCode: (code) => set({ userCode: code }),
      setCustomInput: (input) => set({ customInput: input }),
      setTestResult: (r) => set({ testResult: r }),
      setResult: (r) => set({ result: r }),
      setHintText: (t) => set({ hintText: t }),
      setHintLevel: (l) => set({ hintLevel: l }),
      setShowSolution: (v) => set({ showSolution: v }),
      setSolutionText: (t) => set({ solutionText: t }),
      setDifficulty: (d) => set({ difficulty: d }),
      reset: () =>
        set({
          selected: null, userCode: "# 在此编写你的代码\n", customInput: "",
          testResult: null, result: null, hintText: "", hintLevel: 1,
          showSolution: false, solutionText: "", difficulty: 2,
        }),
    }),
    {
      name: "pytutor-exercise",
      storage: createJSONStorage(() => sessionStorage),
    }
  )
);
