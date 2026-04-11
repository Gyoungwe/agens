import { useEffect, useRef } from 'react'
import { parseSSEStream } from '@/utils/sse'
import { useBioStore } from '@/store/bioStore'
import type { BioWorkflowResponse } from '@/api/bio'
import { getDirectApiBaseUrl } from '@/api/client'

function findStageNameByTraceId(
  stages: Record<string, import('@/types/event').BioStageStatus>,
  traceId: string,
): string | null {
  for (const [stageName, stage] of Object.entries(stages)) {
    if (stage.trace_id === traceId) {
      return stageName
    }
  }
  return null
}

export function useBioEvents() {
  const { stream, clearStream } = useBioStore()
  const abortRef = useRef<AbortController | null>(null)

  const startStream = async (
    goal: string,
    dataset?: string,
    scope_id?: string,
    provider_id?: string,
    continue_on_error = true,
    plan?: any,
    user_input_payload?: Record<string, unknown>,
    resume_from_trace_id?: string,
  ): Promise<BioWorkflowResponse | null> => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
    abortRef.current = new AbortController()

    clearStream()
    useBioStore.getState().setStream({
      session_id: 'pending',
      trace_id: 'pending',
      goal,
      scope_id,
      provider_id,
      total_stages: 5,
      failed_stages: 0,
      isRunning: true,
      stages: {},
      logs: [
        {
          id: crypto.randomUUID(),
          event_type: 'client_start',
          agent_id: 'ui',
          trace_id: 'pending',
          status: 'running',
          message: 'Bio workflow request sent. Waiting for server stream...',
          created_at: Date.now(),
        },
      ],
    })

    const token = localStorage.getItem('token')
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(`${getDirectApiBaseUrl()}/bio/workflow?stream=true`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        goal,
        dataset,
        scope_id,
        provider_id,
        continue_on_error,
        plan,
        user_input_payload,
        resume_from_trace_id,
      }),
      signal: abortRef.current.signal,
    })

    if (!response.ok) {
      let message = `Bio workflow request failed (${response.status})`
      try {
        const text = await response.text()
        if (text) {
          try {
            const parsed = JSON.parse(text) as { detail?: string; message?: string }
            message = parsed.detail || parsed.message || text
          } catch {
            message = text
          }
        }
      } catch (readError) {
        console.warn('Failed to read bio workflow error body', readError)
      }
      throw new Error(message)
    }

    if (!response.body) {
      throw new Error('Bio workflow stream unavailable')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let finalResult: BioWorkflowResponse | null = null

    try {
      for await (const event of parseSSEStream(reader, decoder)) {
        const { eventType, data } = event
        const store = useBioStore.getState()

        if (eventType === 'bio_workflow_start') {
          store.setStream({
            session_id: data.session_id as string,
            trace_id: data.trace_id as string,
            goal: data.goal as string,
            scope_id: data.scope_id as string | undefined,
            provider_id: data.provider_id as string | undefined,
            total_stages: 5,
            failed_stages: 0,
            isRunning: true,
            stages: {},
            logs: [],
          })
        } else if (eventType === 'bio_stage_pending') {
          store.updateStage(data.stage as string, {
            agent_id: data.agent_id as string,
            trace_id: data.trace_id as string,
            status: 'pending',
          })
        } else if (eventType === 'bio_stage_running') {
          store.updateStage(data.stage as string, {
            agent_id: data.agent_id as string,
            trace_id: data.trace_id as string,
            status: 'running',
            waiting_for: 'agent_start',
            last_event: 'bio_stage_running',
          })
        } else if (eventType === 'bio_stage_progress') {
          store.updateStage(data.stage as string, {
            agent_id: data.agent_id as string,
            trace_id: data.trace_id as string,
            status: 'running',
            elapsed_ms: Number(data.elapsed_ms || 0),
            wait_ms: Number(data.elapsed_ms || 0),
            progress_pct: Number(data.progress_pct || 0),
            waiting_for: String(data.waiting_for || 'model_response'),
            last_event: 'bio_stage_progress',
          })
        } else if (eventType === 'bio_stage_done') {
          store.updateStage(data.stage as string, {
            agent_id: data.agent_id as string,
            trace_id: data.trace_id as string,
            status: data.status as 'ok' | 'timeout' | 'error',
            elapsed_ms: data.elapsed_ms as number,
            wait_ms: data.elapsed_ms as number,
            progress_pct: 100,
            waiting_for: null,
            last_event: 'bio_stage_done',
            first_response_received: Boolean(data.output),
            output: data.output as string,
            error: data.error as string | null,
          })
        } else if (eventType === 'bio_workflow_done') {
          store.setRunning(false)
          const cur = store.stream
          if (cur) {
            store.setStream({ ...cur, isRunning: false, failed_stages: data.failed_stages as number })
          }
        } else if (eventType === 'bio_workflow_needs_input') {
          store.setRunning(false)
          const cur = store.stream
          if (cur) {
            store.addLog({
              id: `needs-input-${Date.now()}`,
              created_at: Date.now(),
              event_type: 'bio_workflow_needs_input',
              agent_id: String(data.agent_id || 'harness'),
              trace_id: String(data.trace_id || ''),
              status: 'needs_user_input',
              message: `${String(data.stage || 'workflow')}: ${String(data.user_question || 'Workflow requires user input to continue.')}`,
            })
            store.setStream({ ...cur, isRunning: false })
          }
        } else if (eventType === 'bio_workflow_final') {
          store.setRunning(false)
          finalResult = {
            success: Boolean(data.success),
            status: (data.status as 'success' | 'partial_failure' | 'needs_user_input') || 'partial_failure',
            trace_id: String(data.trace_id || ''),
            session_id: String(data.session_id || ''),
            workflow: String(data.workflow || 'bioinformatics-mvp'),
            scope_id: data.scope_id ? String(data.scope_id) : undefined,
            provider_id: data.provider_id ? String(data.provider_id) : undefined,
            response: String(data.response || ''),
            stage_results: Array.isArray(data.stage_results) ? (data.stage_results as BioWorkflowResponse['stage_results']) : [],
            failed_stages: Number(data.failed_stages || 0),
            total_stages: Number(data.total_stages || 0),
            execution_policy: (data.execution_policy as Record<string, unknown> | undefined),
            needs_user_input: Boolean(data.needs_user_input),
            user_question: data.user_question ? String(data.user_question) : undefined,
            required_fields: Array.isArray(data.required_fields) ? (data.required_fields as string[]) : undefined,
            intent: data.intent as BioWorkflowResponse['intent'],
            plan: data.plan as BioWorkflowResponse['plan'],
          }
          break
        } else if (eventType === 'heartbeat' || eventType === 'error') {
          continue
        } else {
          const traceId = String((data as { meta?: { trace_id?: string } }).meta?.trace_id || '')
          const current = store.stream
          const stageName = current ? findStageNameByTraceId(current.stages, traceId) : null
          if (stageName) {
            const partialUpdate: Partial<import('@/types/event').BioStageStatus> = {
              last_event: eventType,
            }
            if (eventType === 'agent_start') {
              partialUpdate.status = 'running'
              partialUpdate.waiting_for = 'llm_start'
            } else if (eventType === 'agent_thinking') {
              partialUpdate.status = 'running'
              partialUpdate.waiting_for = 'thinking'
            } else if (eventType === 'agent_tool_call') {
              partialUpdate.status = 'running'
              partialUpdate.waiting_for = 'tool_or_llm_call'
            } else if (eventType === 'agent_output') {
              partialUpdate.status = 'running'
              partialUpdate.waiting_for = 'post_processing'
              partialUpdate.first_response_received = true
            } else if (eventType === 'agent_done') {
              partialUpdate.waiting_for = null
            } else if (eventType === 'task_timeout') {
              partialUpdate.status = 'timeout'
              partialUpdate.waiting_for = null
            } else if (eventType === 'task_failed' || eventType === 'error') {
              partialUpdate.status = 'error'
              partialUpdate.waiting_for = null
            }
            store.updateStage(stageName, partialUpdate)
          }

          store.addLog({
            id: String((data as { event_id?: string }).event_id || crypto.randomUUID()),
            event_type: eventType,
            agent_id: String((data as { agent?: string }).agent || 'system'),
            trace_id: traceId,
            status: String((data as { status?: string }).status || ''),
            message: JSON.stringify((data as { data?: unknown }).data || data),
            created_at: Number((data as { created_at?: number }).created_at || Date.now()),
          })
        }
      }
    } finally {
      reader.releaseLock()
    }

    return finalResult
  }

  const cancelStream = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }

  useEffect(() => {
    const current = useBioStore.getState().stream
    if (current?.trace_id === 'pending' && !abortRef.current) {
      clearStream()
    }

    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [clearStream])

  return { stream, startStream, cancelStream, clearStream }
}
