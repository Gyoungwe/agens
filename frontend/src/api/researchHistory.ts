import client from './client'
import type { Session } from '@/types'

export interface SessionResultsResponse {
  session_id: string
  results_count: number
  results: Array<{
    id: number
    session_id: string
    trace_id: string
    agent_id: string
    result: string
    status: string
    created_at: string
  }>
}

export interface ResearchHistoryResponse {
  session_id: string
  title?: string
  status?: 'active' | 'completed' | 'closed' | string
  created_at?: string
  updated_at?: string
  results_count: number
  results: Array<{
    agent_id: string
    result: string
    created_at: string
    trace_id?: string
  }>
}

export const researchHistoryApi = {
  listSessions: () => client.get<Session[]>('/sessions', { params: { kind: 'research' } }),
  getResearchHistory: (sessionId: string) =>
    client.get<ResearchHistoryResponse>(`/research/history/${sessionId}`),
  deleteResearchSession: (sessionId: string) =>
    client.delete(`/research/sessions/${sessionId}`),
  getSessionResults: (sessionId: string) =>
    client.get<SessionResultsResponse>(`/sessions/${sessionId}/results`),
}
