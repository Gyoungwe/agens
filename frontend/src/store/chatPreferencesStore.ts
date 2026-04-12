import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ChatMode = 'auto' | 'chat'
export type MemoryScope = 'session' | 'global'

interface ChatPreferencesState {
  defaultChatMode: ChatMode
  memoryScope: MemoryScope
  realtimeLogsEnabled: boolean
  setDefaultChatMode: (mode: ChatMode) => void
  setMemoryScope: (scope: MemoryScope) => void
  setRealtimeLogsEnabled: (enabled: boolean) => void
}

export const useChatPreferencesStore = create<ChatPreferencesState>()(
  persist(
    (set) => ({
      defaultChatMode: 'auto',
      memoryScope: 'session',
      realtimeLogsEnabled: true,
      setDefaultChatMode: (defaultChatMode) => set({ defaultChatMode }),
      setMemoryScope: (memoryScope) => set({ memoryScope }),
      setRealtimeLogsEnabled: (realtimeLogsEnabled) => set({ realtimeLogsEnabled }),
    }),
    {
      name: 'chat-preferences-storage',
      partialize: (state) => ({
        defaultChatMode: state.defaultChatMode,
        memoryScope: state.memoryScope,
        realtimeLogsEnabled: state.realtimeLogsEnabled,
      }),
    }
  )
)
