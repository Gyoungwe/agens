export type SessionNamespace =
  | 'chat_session'
  | 'research_session'
  | 'workflow_session'
  | 'channel_session'

export type MemoryNamespace =
  | 'chat_memory'
  | 'research_memory'
  | 'workflow_memory'
  | 'shared_knowledge'

export type RuntimeNamespace =
  | 'chat_runtime'
  | 'research_runtime'
  | 'workflow_runtime'
  | 'system_runtime'

export type RuntimeMessageType = 'task' | 'result' | 'error' | 'status'
export type RuntimeContentFormat = 'text' | 'markdown' | 'json'
export type RuntimeOutputType = 'final' | 'partial' | 'report' | 'error'
export const RUNTIME_CONTRACT_VERSION = '1.0' as const

export interface RuntimeSessionContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  session_id: string
  title: string
  status: 'active' | 'completed' | 'closed'
  namespace: SessionNamespace
  created_at: string
  updated_at: string
  metadata: Record<string, unknown>
}

export interface RuntimeMessageContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  id: string
  created_at: string
  sender: string
  recipient: string
  type: RuntimeMessageType
  trace_id: string
  session_id?: string
  correlation_id: string
  namespace?: RuntimeNamespace
  payload: Record<string, unknown>
}

export interface RuntimeTaskPayloadContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  instruction: string
  context: Record<string, unknown>
  priority: number
}

export interface RuntimeResultPayloadContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  success: boolean
  output: unknown
  summary: string
  metadata: Record<string, unknown>
}

export interface RuntimeMemoryRecordContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  id: string
  text: string
  owner: string
  source: string
  created_at: string
  scope_id?: string
  namespace: MemoryNamespace
  metadata: Record<string, unknown>
}

export interface RuntimeEventContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  event_id: string
  task_id: string
  session_id?: string
  correlation_id: string
  created_at: number
  type: string
  agent: string
  status: string
  namespace?: RuntimeNamespace
  meta: Record<string, unknown>
  data: Record<string, unknown>
}

export interface RuntimeCitationContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  text: string
  type: 'paper' | 'website' | 'other'
  link?: string
}

export interface RuntimeOutputContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  session_id?: string
  trace_id?: string
  namespace: RuntimeNamespace
  output_type: RuntimeOutputType
  content: string
  content_format: RuntimeContentFormat
  summary_format?: 'text' | 'json'
  citations: RuntimeCitationContract[]
  metadata: Record<string, unknown>
}

export interface RuntimeWorkflowBoundaryContract {
  contract_version: typeof RUNTIME_CONTRACT_VERSION
  workflow_family: string
  intent_contract: 'WorkflowIntentSpec'
  plan_contract: 'WorkflowPlanSpec'
  stage_contract: 'WorkflowStageSpec'
  report_contract: 'ReportSpec'
  evolution_contract: 'EvolutionSpec'
}
