import { create } from 'zustand'
import type { Agent, AgentEvent } from '@/types'

interface AgentState {
  agents: Agent[]
  selectedAgentId: string | null
  agentEvents: AgentEvent[]
  setAgents: (agents: Agent[]) => void
  updateAgentStatus: (agentId: string, status: Agent['status']) => void
  setSelectedAgent: (agentId: string | null) => void
  addEvent: (event: AgentEvent) => void
  clearEvents: () => void
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  selectedAgentId: null,
  agentEvents: [],

  setAgents: (agents) => set({ agents }),

  updateAgentStatus: (agentId, status) =>
    set((state) => ({
      agents: state.agents.map((agent) =>
        agent.agent_id === agentId ? { ...agent, status } : agent
      ),
    })),

  setSelectedAgent: (agentId) => set({ selectedAgentId: agentId }),

  addEvent: (event) =>
    set((state) => ({
      agentEvents: [...state.agentEvents.slice(-50), event],
    })),

  clearEvents: () => set({ agentEvents: [] }),
}))
