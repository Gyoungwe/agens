export interface Agent {
  agent_id: string
  name: string
  role: string
  status: 'idle' | 'running' | 'waiting'
  skills: string[]
  model?: string
  priority?: 'high' | 'normal' | 'low'
  meta?: {
    name?: string
    role?: string
    provider?: string
    model?: string
    max_tokens?: number
    skills?: string[]
    system_prompt?: string
  }
}

export interface AgentEvent {
  type: 'start' | 'thinking' | 'tool' | 'output' | 'done' | 'error'
  agent_id: string
  message: string
  timestamp: string
}

export interface AgentStatus {
  agent_id: string
  status: 'idle' | 'running' | 'waiting'
  current_task?: string
  last_active?: string
}
