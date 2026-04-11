import { useCallback, useEffect, useRef } from 'react'
import { useAgentStore, useApprovalStore } from '@/store'
import type { WebSocketEvent, Approval } from '@/types/event'
import { useBioStore } from '@/store/bioStore'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const { updateAgentStatus, addEvent } = useAgentStore()
  const { addApproval } = useApprovalStore()
  const { updateStage, setRunning } = useBioStore()

  const connect = useCallback(() => {
    const establishConnection = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/events`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        reconnectAttemptRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data: WebSocketEvent = JSON.parse(event.data)

          if (data.type === 'bio_workflow_start') {
            const d = data as unknown as { type: string; data: { session_id: string; trace_id: string; goal: string; scope_id?: string; provider_id?: string } }
            useBioStore.getState().setStream({
              session_id: d.data.session_id,
              trace_id: d.data.trace_id,
              goal: d.data.goal,
              scope_id: d.data.scope_id,
              provider_id: d.data.provider_id,
              total_stages: 5,
              failed_stages: 0,
              isRunning: true,
              stages: {},
              logs: [],
            })
          } else if (data.type === 'bio_stage_pending' || data.type === 'bio_stage_running') {
            const d = data as unknown as { type: string; data: { stage: string; agent_id: string; trace_id: string } }
            updateStage(d.data.stage, {
              agent_id: d.data.agent_id,
              trace_id: d.data.trace_id,
              status: d.type === 'bio_stage_pending' ? 'pending' : 'running',
            })
            setRunning(true)
          } else if (data.type === 'bio_stage_done') {
            const d = data as unknown as { type: string; data: { stage: string; agent_id: string; trace_id: string; status: string; elapsed_ms: number; output: string; error: string | null } }
            updateStage(d.data.stage, {
              agent_id: d.data.agent_id,
              trace_id: d.data.trace_id,
              status: d.data.status as 'ok' | 'timeout' | 'error',
              elapsed_ms: d.data.elapsed_ms,
              output: d.data.output,
              error: d.data.error,
            })
          } else if (data.type === 'bio_workflow_done') {
            const d = data as unknown as { type: string; data: { failed_stages: number } }
            setRunning(false)
            const current = useBioStore.getState()
            if (current.stream) {
              useBioStore.setState({
                stream: { ...current.stream, isRunning: false, failed_stages: d.data.failed_stages },
              })
            }
          } else if (data.type === 'agent_status_changed') {
            const statusData = data as unknown as { type: string; data: { agent_id: string; status: 'idle' | 'running' | 'waiting'; current_task?: string } }
            updateAgentStatus(
              statusData.data.agent_id,
              statusData.data.status
            )
          } else if (data.type === 'approval_created') {
            const approvalData = data as unknown as { type: string; data: Approval }
            addApproval(approvalData.data)
          }

          addEvent({
            type: 'done' as const,
            agent_id: (data as unknown as { data: { agent_id?: string } }).data?.agent_id || 'system',
            message: JSON.stringify(data.data),
            timestamp: data.timestamp,
          })
        } catch (error) {
          console.error('[WebSocket] Parse error:', error)
        }
      }

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected, reconnecting...')
        const attempt = reconnectAttemptRef.current
        const baseDelay = 1000
        const maxDelay = 30000
        const exponentialDelay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay)
        const jitter = Math.random() * 500
        const delay = Math.floor(exponentialDelay + jitter)
        reconnectAttemptRef.current = attempt + 1
        reconnectTimeoutRef.current = setTimeout(() => {
          establishConnection()
        }, delay)
      }

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
      }
    }

    establishConnection()
  }, [updateAgentStatus, addApproval, addEvent, updateStage, setRunning])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return { connect, disconnect }
}
