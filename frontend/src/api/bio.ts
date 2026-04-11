import client, { getDirectApiBaseUrl } from './client'

export interface WorkflowIntentSpec {
  request_id?: string
  goal: string
  assay_type: string
  analysis_type?: string
  dataset?: string
  input_assets?: Array<{ kind: string; path: string; sample_id?: string; paired_end?: boolean }>
  sample_sheet?: {
    sample_count?: number
    groups?: string[]
    has_control?: boolean
    design_summary?: string
  }
  reference_bundle?: {
    genome?: string
    annotation?: string
    dbs?: string[]
  }
  expected_outputs: string[]
  constraints?: {
    time_budget?: string
    compute_budget?: string
    privacy_level?: 'low' | 'medium' | 'high'
    internet_allowed?: boolean
  }
  fields_requiring_confirmation: string[]
  user_confirmed: boolean
  system_inference?: {
    inferred_assay_type?: string
    inferred_workflow_family?: string
    inferred_risks: string[]
    confidence: number
  }
}

export interface WorkflowPlanStage {
  id: string
  name: string
  agent_id?: string
  kind: string
  depends_on: string[]
  outputs: string[]
  prompt_template?: string
}

export interface WorkflowPlanSpec {
  plan_id?: string
  intent_id?: string
  workflow_family: string
  stages: WorkflowPlanStage[]
}

export interface BioStageResult {
  stage: string
  agent_id: string
  status: 'ok' | 'timeout' | 'error'
  elapsed_ms: number
  trace_id: string
  error: string | null
  output: string
  provenance?: {
    inputs: Record<string, unknown>
    params: Record<string, unknown>
    provider_id: string | null
    elapsed_ms: number
  }
}

export interface BioWorkflowResponse {
  success: boolean
  status: 'success' | 'partial_failure'
  trace_id: string
  session_id: string
  workflow: string
  scope_id?: string
  provider_id?: string
  provider_fallback?: boolean
  response: string
  stage_results: BioStageResult[]
  failed_stages: number
  total_stages: number
  execution_policy?: Record<string, unknown>
  intent?: WorkflowIntentSpec
  plan?: WorkflowPlanSpec
}

export interface PlanGenerateResponse {
  success: boolean
  intent: WorkflowIntentSpec
  plan: WorkflowPlanSpec
}

export interface ConfirmIntentResponse {
  success: boolean
  intent: WorkflowIntentSpec
  requires_confirmation: boolean
  workflow_family: string
}

export const bioApi = {
  runWorkflow: (
    data: {
      goal: string
      dataset?: string
      scope_id?: string
      provider_id?: string
      session_id?: string
      continue_on_error?: boolean
      plan?: WorkflowPlanSpec
      intent?: WorkflowIntentSpec
    }
  ) => client.post<BioWorkflowResponse>('/bio/workflow', data),

  runWorkflowStream: (data: {
    goal: string
    dataset?: string
    scope_id?: string
    provider_id?: string
      session_id?: string
      continue_on_error?: boolean
      plan?: WorkflowPlanSpec
      intent?: WorkflowIntentSpec
    }) => {
    const params = new URLSearchParams({ stream: 'true' })
    if (data.session_id) params.set('session_id', data.session_id)
    return fetch(`${getDirectApiBaseUrl()}/bio/workflow?${params}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
      },
      body: JSON.stringify({
        goal: data.goal,
        dataset: data.dataset,
        scope_id: data.scope_id,
        provider_id: data.provider_id,
        continue_on_error: data.continue_on_error,
        plan: data.plan,
        intent: data.intent,
      }),
    })
  },

  confirmIntent: (data: {
    goal: string
    dataset?: string
    intent?: Partial<WorkflowIntentSpec>
  }) => client.post<ConfirmIntentResponse>('/bio/intent/confirm', data),

  generatePlan: (data: {
    goal?: string
    dataset?: string
    intent: WorkflowIntentSpec
  }) => client.post<PlanGenerateResponse>('/bio/plan/generate', data),
}
