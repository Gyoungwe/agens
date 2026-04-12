import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout'
import { agentsApi, client } from '@/api'
import { Plus } from 'lucide-react'

interface AgentSkillItem {
  skill_id: string
  name: string
  description: string
  enabled: boolean
  assigned: boolean
}

export function AgentSettingsPage() {
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [newMemory, setNewMemory] = useState('')

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => (await agentsApi.getAgents()).data,
  })

  const defaultAgentId = agentsData?.agents?.[0]?.agent_id || ''
  const activeAgent = selectedAgent || defaultAgentId

  const { data: skillData, refetch: refetchSkills } = useQuery({
    queryKey: ['agent-skills-all', activeAgent],
    enabled: !!activeAgent,
    queryFn: async () => (await agentsApi.getAllSkillsForAgent(activeAgent)).data,
  })

  const { data: memoryData, refetch: refetchMemory } = useQuery({
    queryKey: ['agent-memory', activeAgent],
    enabled: !!activeAgent,
    queryFn: async () => (await client.get('/memory/', { params: { owner: activeAgent, limit: 30 } })).data,
  })

  // Split skills into Default (unassigned) and Assigned (registry-assigned) for clearer UI
  const allSkills: Array<AgentSkillItem> = skillData?.skills || []
  const defaultSkillsList = allSkills.filter((s) => !s.assigned)
  const assignedSkillsList = allSkills.filter((s) => s.assigned)

  const bindMutation = useMutation({
    mutationFn: async ({ skillId, assigned }: { skillId: string; assigned: boolean }) => {
      if (assigned) {
         await agentsApi.unassignSkill(activeAgent, skillId)
       } else {
         await agentsApi.assignSkill(activeAgent, skillId)
       }
    },
    onSuccess: () => refetchSkills(),
  })

  const addMemoryMutation = useMutation({
    mutationFn: async () => {
      await client.post('/memory/', null, {
        params: {
          text: newMemory,
          owner: activeAgent,
          session_id: `agent-settings-${activeAgent}`,
          source: 'agent-settings-ui',
        },
      })
    },
    onSuccess: () => {
      setNewMemory('')
      refetchMemory()
    },
  })

  const deleteMemoryMutation = useMutation({
    mutationFn: async (memoryId: string) => {
      await client.delete(`/memory/${memoryId}`)
    },
    onSuccess: () => refetchMemory(),
  })

  return (
    <div className="flex flex-col h-full">
      <Header title="Agent Settings" />
      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4 p-4">
        <div className="glass-card rounded-2xl p-4 overflow-y-auto">
          <h3 className="text-sm font-semibold mb-3">Agents</h3>
          <div className="space-y-2">
            {(agentsData?.agents || []).map((agent: { agent_id: string; name?: string; role?: string }) => (
              <button
                key={agent.agent_id}
                onClick={() => setSelectedAgent(agent.agent_id)}
                className={`w-full text-left p-3 rounded-xl border transition-colors ${
                  activeAgent === agent.agent_id ? 'border-primary bg-primary/10' : 'border-border hover:bg-secondary/50'
                }`}
              >
                <div className="font-medium text-sm">{agent.name || agent.agent_id}</div>
                <div className="text-xs text-muted-foreground">{agent.role || agent.agent_id}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-y-auto space-y-4 pr-1">
          <div className="glass-card rounded-2xl p-4">
            <h3 className="text-sm font-semibold mb-3">Skill Binding</h3>
            <div className="space-y-2">
              {/* Default (unassigned) skills */}
              {defaultSkillsList.length > 0 && (
                <div className="mb-2 text-xs text-muted-foreground">Default Skills</div>
              )}
              {defaultSkillsList.map((skill) => (
                <div key={skill.skill_id} className="flex items-center justify-between border border-border rounded-xl p-3">
                  <div>
                    <div className="text-sm font-medium">{skill.name}</div>
                    <div className="text-xs text-muted-foreground">{skill.description || skill.skill_id}</div>
                  </div>
                  <button
                    onClick={() => bindMutation.mutate({ skillId: skill.skill_id, assigned: false })}
                    disabled={bindMutation.isPending || !skill.enabled}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-secondary text-foreground disabled:opacity-50`}
                  >
                    Assign
                  </button>
                </div>
              ))}

              {/* Assigned (registry) skills */}
              {assignedSkillsList.length > 0 && (
                <>
                  <div className="mt-2 mb-2 text-xs text-muted-foreground">Assigned Skills</div>
                  {assignedSkillsList.map((skill) => (
                    <div key={skill.skill_id} className="flex items-center justify-between border border-border rounded-xl p-3">
                      <div>
                        <div className="text-sm font-medium">{skill.name}</div>
                        <div className="text-xs text-muted-foreground">{skill.description || skill.skill_id}</div>
                      </div>
                      <button
                        onClick={() => bindMutation.mutate({ skillId: skill.skill_id, assigned: true })}
                        disabled={bindMutation.isPending || !skill.enabled}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-primary text-white disabled:opacity-50`}
                      >
                        Unassign
                      </button>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          <div className="glass-card rounded-2xl p-4">
            <h3 className="text-sm font-semibold mb-3">Agent Memory</h3>
            <div className="flex gap-2 mb-3">
              <input
                value={newMemory}
                onChange={(e) => setNewMemory(e.target.value)}
                placeholder="Add memory for this agent"
                className="flex-1 px-3 py-2 rounded-xl border border-border bg-card text-sm"
              />
              <button
                onClick={() => addMemoryMutation.mutate()}
                disabled={!newMemory.trim() || addMemoryMutation.isPending || !activeAgent}
                className="px-3 py-2 rounded-xl bg-primary text-white disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 max-h-80 overflow-y-auto">
              {(memoryData?.memories || []).map((m: { id: string; text?: string; content?: string; created_at: string }) => (
                <div key={m.id} className="border border-border rounded-xl p-3">
                  <div className="text-sm line-clamp-3">{m.text || m.content || ''}</div>
                  <div className="flex items-center justify-between mt-2">
                    <div className="text-xs text-muted-foreground">{new Date(m.created_at).toLocaleString()}</div>
                    <button
                      onClick={() => deleteMemoryMutation.mutate(m.id)}
                      className="text-xs text-destructive"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
