import { useCallback, useEffect, useRef } from 'react'
import { useAgentStore, useApprovalStore } from '@/store'
import type { WebSocketEvent, Approval } from '@/types/event'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const { updateAgentStatus, addEvent } = useAgentStore()
  const { addApproval } = useApprovalStore()

  const connect = useCallback(() => {
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

        if (data.type === 'agent_status_changed') {
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
      reconnectTimeoutRef.current = setTimeout(connect, delay)
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
    }
  }, [updateAgentStatus, addApproval, addEvent])

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
