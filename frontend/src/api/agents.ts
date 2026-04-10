import client from './client'
import type { Agent, AgentStatus } from '@/types'

export const agentsApi = {
  getAgents: () =>
    client.get<{ agents: Agent[] }>('/agents/'),

  getAgent: (agentId: string) =>
    client.get<{ agent: Agent }>(`/agents/${agentId}`),

  getAgentStatus: () =>
    client.get<{ agents: AgentStatus[] }>('/agents/status'),

  getAgentMessages: (agentId: string) =>
    client.get<{ messages: unknown[] }>(`/agents/${agentId}/messages`),

  updateAgentSoul: (agentId: string, data: { meta: Record<string, unknown>; body: string }) =>
    client.put(`/agents/${agentId}/soul`, data),

  getBackups: (agentId: string) =>
    client.get<{ backups: { name: string; created_at: string }[] }>(`/agents/${agentId}/backups`),

  restoreBackup: (agentId: string, backupName: string) =>
    client.post(`/agents/${agentId}/backups/${backupName}/restore`),
}
