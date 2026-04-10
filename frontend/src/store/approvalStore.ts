import { create } from 'zustand'
import type { Approval } from '@/types'

interface ApprovalState {
  approvals: Approval[]
  pendingCount: number
  setApprovals: (approvals: Approval[]) => void
  addApproval: (approval: Approval) => void
  updateApproval: (id: string, status: Approval['status']) => void
}

export const useApprovalStore = create<ApprovalState>((set) => ({
  approvals: [],
  pendingCount: 0,

  setApprovals: (approvals) =>
    set({
      approvals,
      pendingCount: approvals.filter((a) => a.status === 'pending').length,
    }),

  addApproval: (approval) =>
    set((state) => ({
      approvals: [approval, ...state.approvals],
      pendingCount: state.pendingCount + 1,
    })),

  updateApproval: (id, status) =>
    set((state) => ({
      approvals: state.approvals.map((a) =>
        a.id === id ? { ...a, status, updated_at: new Date().toISOString() } : a
      ),
      pendingCount:
        status !== 'pending'
          ? state.pendingCount
          : state.approvals.filter((a) => a.status === 'pending').length,
    })),
}))
