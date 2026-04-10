import { create } from 'zustand'
import type { Message, Session } from '@/types'

interface ChatState {
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  setSessions: (sessions: Session[]) => void
  setCurrentSession: (sessionId: string | null) => void
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  updateMessage: (id: string, updates: Partial<Message>) => void
  setLoading: (loading: boolean) => void
  setStreaming: (streaming: boolean) => void
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  isLoading: false,
  isStreaming: false,

  setSessions: (sessions) => set({ sessions }),

  setCurrentSession: (sessionId) => set({ currentSessionId: sessionId }),

  setMessages: (messages) => set({ messages }),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    })),

  setLoading: (isLoading) => set({ isLoading }),

  setStreaming: (isStreaming) => set({ isStreaming }),
}))
