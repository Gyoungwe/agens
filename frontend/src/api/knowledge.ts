import client from './client'

export interface KnowledgeDocument {
  id: string
  filename: string
  owner: string
  source: string
  created_at: string
}

export interface ImportProgress {
  status: 'parsing' | 'chunking' | 'vectorizing' | 'done' | 'error'
  progress: number
  message: string
}

export const knowledgeApi = {
  getDocuments: (params?: { owner?: string; limit?: number }) =>
    client.get<{ documents: KnowledgeDocument[]; total: number }>('/memory/', { params }),

  searchDocuments: (params: { query: string; top_k?: number; owner?: string }) =>
    client.get<{ results: { text: string; score: number; owner: string }[] }>('/memory/search', { params }),

  importDocument: (data: { text: string; filename: string; owner: string; source: string }) =>
    client.post<{ task_id: string }>('/knowledge/import', data),

  getImportProgress: (taskId: string) =>
    new EventSource(`/api/knowledge/import/${taskId}/progress`),
}
