import client from './client'

export interface Approval {
  id: string
  agent_id: string
  skill_id: string
  skill_name: string
   kind?: string
   summary?: string
   provider_id?: string
   scope_id?: string
   workflow_trace_id?: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  updated_at?: string
}

interface EvolutionApprovalResponse {
  request_id: string
  agent_id: string
  changes: Record<string, unknown>
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  reviewed_at?: string
}

const normalizeApproval = (item: EvolutionApprovalResponse): Approval => ({
  id: item.request_id,
  agent_id: item.agent_id,
  skill_id: String((item.changes as { skill?: unknown })?.skill || ''),
  skill_name: String((item.changes as { skill?: unknown; kind?: unknown })?.skill || (item.changes as { kind?: unknown })?.kind || ''),
  kind: String((item.changes as { kind?: unknown })?.kind || ''),
  summary: String((item.changes as { summary?: unknown })?.summary || ''),
  provider_id: String((item.changes as { provider_id?: unknown })?.provider_id || ''),
  scope_id: String((item.changes as { scope_id?: unknown })?.scope_id || ''),
  workflow_trace_id: String((item.changes as { workflow_trace_id?: unknown })?.workflow_trace_id || ''),
  reason: item.reason,
  status: item.status,
  created_at: item.created_at,
  updated_at: item.reviewed_at,
})

export const approvalsApi = {
  getApprovals: async (status?: 'pending' | 'approved' | 'rejected') => {
    const response = await client.get<{ approvals: EvolutionApprovalResponse[] }>('/evolution/approvals', {
      params: { status },
    })
    return {
      ...response,
      data: {
        approvals: (response.data.approvals || []).map(normalizeApproval),
      },
    }
  },

  approve: (id: string) =>
    client.post<{ success: boolean }>(`/evolution/approvals/${id}/approve`),

  reject: (id: string) =>
    client.post<{ success: boolean }>(`/evolution/approvals/${id}/reject`),
}
