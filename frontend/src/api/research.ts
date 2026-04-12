import client from './client'
import type { RuntimeOutputContract } from '@/types'

export interface ResearchRunResponse extends Omit<RuntimeOutputContract, 'namespace' | 'output_type' | 'content' | 'content_format'> {
  success: boolean
  session_id?: string
  query: string
  research: string
  summary: string
  summary_format?: 'text' | 'json'
  namespace?: 'research_runtime'
  output_type?: 'report' | 'final'
  content?: string
  content_format?: 'text' | 'markdown'
}

export interface ResearchStreamEvent {
  event: string
  trace_id?: string
  session_id?: string
  query?: string
  stage?: string
  message?: string
  source?: string
  source_type?: 'website' | 'paper' | 'other'
  source_link?: string
  source_items?: Array<{ text: string; type: 'website' | 'paper' | 'other'; link?: string }>
  point?: string
  research?: string
  summary?: string
  summary_format?: 'text' | 'json'
  sources?: string[]
  knowledge?: string[]
}

export const researchApi = {
  run: (data: { query: string; session_id?: string; provider_id?: string }) =>
    client.post<ResearchRunResponse>('/research/run', data),

  stream: async (data: { query: string; session_id?: string; provider_id?: string; signal?: AbortSignal }) =>
    fetch('/api/research/stream', {
      method: 'POST',
      signal: data.signal,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
      },
      body: JSON.stringify({
        query: data.query,
        session_id: data.session_id,
        provider_id: data.provider_id,
      }),
    }),
}
