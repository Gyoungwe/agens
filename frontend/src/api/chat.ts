import client from './client'
import type { Message, Session, ChatRequest, ChatResponse } from '@/types'

export const chatApi = {
  sendMessage: (data: ChatRequest) =>
    client.post<ChatResponse>('/chat/stream', data),

  getSessions: () =>
    client.get<{ sessions: Session[] }>('/sessions'),

  getSession: (sessionId: string) =>
    client.get<{ messages: Message[] }>(`/sessions/${sessionId}`),

  deleteSession: (sessionId: string) =>
    client.delete(`/sessions/${sessionId}`),
}
