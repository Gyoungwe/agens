import client from './client'
import type { Agent, AgentStatus } from '@/types'

export const agentsApi = {
  getAgents: () =>
    client.get<{ agents: Agent[] }>('/agents/'),

  getAgent: (agentId: string) =>
    client.get<{ agent: Agent }>(`/agents/${agentId}`),

  getAgentStatus: () =>
    client.get<{ agents: AgentStatus[] }>('/agents/'),

  updateAgentSoul: (agentId: string, data: { meta: Record<string, unknown>; body: string }) =>
    client.put(`/agents/${agentId}/soul`, data),

  getBackups: (agentId: string) =>
    client.get<{ backups: { name: string; created_at: string }[] }>(`/agents/${agentId}/backups`),

  restoreBackup: (agentId: string, backupName: string) =>
    client.post(`/agents/${agentId}/backups/${backupName}/restore`),

  chatWithAgent: (agentId: string, data: { message: string; session_id?: string }) =>
    client.post<{ success: boolean; response: string; session_id: string }>(`/agents/${agentId}/chat`, data),

  getAllSkillsForAgent: (agentId: string) =>
    client.get<{
      success: boolean
      skills: Array<{
        skill_id: string
        name: string
        description: string
        enabled: boolean
        assigned: boolean
        agent_ids: string[]
      }>
    }>(`/agents/${agentId}/skills/all`),

  assignSkill: (agentId: string, skillId: string) =>
    client.post(`/agents/${agentId}/skills/${skillId}/assign`),

  unassignSkill: (agentId: string, skillId: string) =>
    client.post(`/agents/${agentId}/skills/${skillId}/unassign`),
}
