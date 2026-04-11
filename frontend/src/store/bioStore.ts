import { create } from 'zustand'
import type { BioStreamStatus, BioStageStatus, BioEventLog } from '@/types/event'

interface BioState {
  stream: BioStreamStatus | null
  setStream: (s: BioStreamStatus) => void
  updateStage: (stageName: string, update: Partial<BioStageStatus>) => void
  addLog: (log: BioEventLog) => void
  setRunning: (isRunning: boolean) => void
  clearStream: () => void
}

export const useBioStore = create<BioState>((set) => ({
  stream: null,

  setStream: (s) =>
    set({ stream: s }),

  updateStage: (stageName, update) =>
    set((state) => {
      if (!state.stream) return {}
      const stages = { ...state.stream.stages }
      if (!stages[stageName]) {
        stages[stageName] = {
          stage: stageName,
          agent_id: update.agent_id || '',
          trace_id: update.trace_id || '',
          status: 'pending',
          elapsed_ms: 0,
          wait_ms: 0,
          progress_pct: 0,
          waiting_for: null,
          last_event: null,
          first_response_received: false,
          output: '',
          error: null,
        }
      }
      stages[stageName] = { ...stages[stageName], ...update }
      return {
        stream: {
          ...state.stream,
          stages,
          isRunning: update.status === 'pending' || update.status === 'running'
            ? true
            : state.stream.isRunning,
        },
      }
    }),

  addLog: (log) =>
    set((state) => {
      if (!state.stream) return {}
      return {
        stream: {
          ...state.stream,
          logs: [log, ...state.stream.logs].slice(0, 80),
        },
      }
    }),

  setRunning: (isRunning) =>
    set((state) =>
      state.stream ? { stream: { ...state.stream, isRunning } } : {}
    ),

  clearStream: () => set({ stream: null }),
}))
