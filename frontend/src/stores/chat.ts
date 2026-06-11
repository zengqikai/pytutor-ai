"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface Message {
  role: "user" | "assistant";
  content: string;
  response_type?: string;
  hint_level?: number;
  related_concepts?: string[];
  misconception_id?: string;
  pedagogical_strategy?: string;
}

interface ChatState {
  activeSession: string | null;
  messages: Message[];
  setActiveSession: (id: string | null) => void;
  setMessages: (msgs: Message[]) => void;
  addMessage: (msg: Message) => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      activeSession: null,
      messages: [],
      setActiveSession: (id) => set({ activeSession: id }),
      setMessages: (msgs) => set({ messages: msgs }),
      addMessage: (msg) => set({ messages: [...get().messages, msg] }),
      reset: () => set({ activeSession: null, messages: [] }),
    }),
    {
      name: "pytutor-chat",
      storage: createJSONStorage(() => sessionStorage),
      skipHydration: false,
    }
  )
);
