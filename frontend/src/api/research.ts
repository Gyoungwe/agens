import client from './client'

export interface ResearchRunResponse {
  success: boolean
  session_id?: string
  query: string
  research: string
  summary: string
}

export const researchApi = {
  run: (data: { query: string; session_id?: string; provider_id?: string }) =>
    client.post<ResearchRunResponse>('/research/run', data),
}
