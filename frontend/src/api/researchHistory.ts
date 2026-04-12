import client from './client'
import type { Message, Session } from '@/types'

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

export interface ChatHistoryResponse {
  session_id: string
  title?: string
  status?: 'active' | 'completed' | 'closed' | string
  created_at?: string
  updated_at?: string
  message_count?: number
  messages: Message[]
}

export const researchHistoryApi = {
  listSessions: () => client.get<Session[]>('/sessions'),
  getChatHistory: (sessionId: string) =>
    client.get<ChatHistoryResponse>(`/chat/history/${sessionId}`),
  getSessionResults: (sessionId: string) =>
    client.get<SessionResultsResponse>(`/debug/results/${sessionId}`),
}
