import client from './client'

export interface ResearchRunResponse {
  success: boolean
  session_id?: string
  query: string
  research: string
  summary: string
}

export interface ResearchStreamEvent {
  event: string
  trace_id?: string
  session_id?: string
  query?: string
  stage?: string
  message?: string
  source?: string
  point?: string
  research?: string
  summary?: string
  sources?: string[]
  knowledge?: string[]
}

export const researchApi = {
  run: (data: { query: string; session_id?: string; provider_id?: string }) =>
    client.post<ResearchRunResponse>('/research/run', data),

  stream: async (data: { query: string; session_id?: string; provider_id?: string }) =>
    fetch('/api/research/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
      },
      body: JSON.stringify(data),
    }),
}
