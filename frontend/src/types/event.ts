export type EventType =
  | 'agent_status_changed'
  | 'approval_created'
  | 'approval_completed'
  | 'task_progress'
  | 'memory_updated'
  | 'session_updated'

export interface WebSocketEvent {
  type: EventType
  data: unknown
  timestamp: string
}

export interface ApprovalEvent extends WebSocketEvent {
  type: 'approval_created' | 'approval_completed'
  data: Approval
}

export interface AgentStatusEvent extends WebSocketEvent {
  type: 'agent_status_changed'
  data: {
    agent_id: string
    status: 'idle' | 'running' | 'waiting'
    current_task?: string
  }
}

export interface Approval {
  id: string
  agent_id: string
  skill_id: string
  skill_name?: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  updated_at?: string
}
