import client from './client'
import type { Message, Session, ChatRequest, ChatResponse } from '@/types'

export const chatApi = {
  sendMessage: (data: ChatRequest) =>
    client.post<ChatResponse>('/chat/stream', data),

  getSessions: () =>
    client.get<Session[]>('/sessions', { params: { kind: 'chat' } }),

  getSession: (sessionId: string) =>
    client.get<{ messages: Message[] }>(`/sessions/${sessionId}`),

  deleteSession: (sessionId: string) =>
    client.delete(`/sessions/${sessionId}`),

  createSession: (title: string, kind: 'chat' | 'research' = 'chat') =>
    client.post<{ session_id: string; title: string; kind: string }>(`/sessions?title=${encodeURIComponent(title)}&kind=${kind}`),
}
