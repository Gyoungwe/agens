import type { RuntimeEventContract, RuntimeOutputContract } from './runtime'

export type EventType =
  | 'agent_status_changed'
  | 'approval_created'
  | 'approval_completed'
  | 'task_progress'
  | 'memory_updated'
  | 'session_updated'
  | 'bio_stage_pending'
  | 'bio_stage_running'
  | 'bio_stage_progress'
  | 'bio_stage_done'
  | 'bio_workflow_start'
  | 'bio_workflow_done'

export interface WebSocketEvent extends Omit<RuntimeEventContract, 'event_id' | 'task_id' | 'agent' | 'created_at' | 'status' | 'meta' | 'data'> {
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
  kind?: string
  summary?: string
  provider_id?: string
  scope_id?: string
  workflow_trace_id?: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  updated_at?: string
}

export interface BioStageStatus {
  stage: string
  agent_id: string
  trace_id: string
  status: 'pending' | 'running' | 'ok' | 'timeout' | 'error'
  elapsed_ms: number
  wait_ms?: number
  progress_pct?: number
  waiting_for?: string | null
  last_event?: string | null
  first_response_received?: boolean
  output: string
  error: string | null
  provenance?: {
    inputs: Record<string, unknown>
    params: Record<string, unknown>
    provider_id: string | null
    elapsed_ms: number
  }
}

export interface BioEventLog extends Omit<RuntimeEventContract, 'event_id' | 'task_id' | 'type' | 'agent' | 'data' | 'meta' | 'contract_version' | 'correlation_id'> {
  id: string
  event_type: string
  agent_id: string
  trace_id: string
  message: string
  contract_version?: string
  correlation_id?: string
}

export interface BioRuntimeOutput extends Omit<RuntimeOutputContract, 'output_type' | 'content'> {
  output_type: 'report' | 'final'
  content: string
}

export interface BioStreamStatus {
  session_id: string
  trace_id: string
  goal: string
  scope_id?: string
  provider_id?: string
  total_stages: number
  failed_stages: number
  isRunning: boolean
  stages: Record<string, BioStageStatus>
  logs: BioEventLog[]
}
