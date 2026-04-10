import client from './client'

export interface Approval {
  id: string
  agent_id: string
  skill_id: string
  skill_name: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  updated_at?: string
}

export const approvalsApi = {
  getApprovals: (status?: 'pending' | 'approved' | 'rejected') =>
    client.get<{ approvals: Approval[] }>('/approvals', { params: { status } }),

  approve: (id: string) =>
    client.post<{ success: boolean }>(`/approvals/${id}/approve`),

  reject: (id: string) =>
    client.post<{ success: boolean }>(`/approvals/${id}/reject`),
}
