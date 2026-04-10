import { useState, useRef, useEffect } from 'react'
import { Header } from '@/components/layout'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { InvocationTrace } from '@/components/chat/InvocationTrace'
import { useChatStore } from '@/store'
import { parseSSEStream } from '@/utils/sse'
import type { Message } from '@/types'
import type { TraceEvent } from '@/components/chat/InvocationTrace'

export function ChatPage() {
  const [splitPosition, setSplitPosition] = useState(60)
  const containerRef = useRef<HTMLDivElement>(null)
  const { messages, isStreaming, currentSessionId, setSessions, setCurrentSession, addMessage, updateMessage, setStreaming } = useChatStore()
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([])

  useEffect(() => {
    fetch('/api/sessions')
      .then((res) => res.json())
      .then((data) => {
        const sessions = Array.isArray(data) ? data : (data.sessions || [])
        setSessions(sessions)
        if (sessions.length > 0) {
          setCurrentSession(sessions[0].session_id)
        }
      })
  }, [setSessions, setCurrentSession])

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return

    setTraceEvents([])

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user' as const,
      content: message,
      created_at: new Date().toISOString(),
      session_id: currentSessionId || undefined,
    }
    addMessage(userMessage)
    setStreaming(true)

    const assistantId = `assistant-${Date.now()}`
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      session_id: currentSessionId || undefined,
    })

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          message,
          session_id: currentSessionId,
        }),
      })

      if (!response.ok) {
        const text = await response.text()
        throw new Error(`HTTP ${response.status}: ${text}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response stream received')
      }

      const decoder = new TextDecoder()
      let finalResponse = ''
      let traceId = ''

      for await (const sseEvent of parseSSEStream(reader, decoder)) {
        traceId = (sseEvent.data.trace_id as string) || traceId

        const eventData = sseEvent.data as Record<string, unknown>
        setTraceEvents((prev) => [
          ...prev,
          {
            event_id: String(sseEvent.eventType) + '-' + Date.now() + '-' + Math.random(),
            type: sseEvent.eventType,
            agent: String(eventData.agent || ''),
            status: String(eventData.status || 'running'),
            data: eventData,
            created_at: Date.now() / 1000,
          },
        ])

        if (sseEvent.eventType === 'final_response') {
          finalResponse = ((eventData.data as Record<string, unknown>)?.response as string) || ''
        } else if (sseEvent.eventType === 'task_failed' || sseEvent.eventType === 'task_timeout') {
          const err = (eventData.error as string) || (eventData.message as string) || sseEvent.eventType
          throw new Error(`${sseEvent.eventType}: ${err}`)
        } else if (sseEvent.eventType === 'error') {
          throw new Error((eventData.message as string) || (eventData.error as string) || 'stream error')
        }
      }

      if (!finalResponse) {
        throw new Error(`No final_response received${traceId ? ` (trace_id=${traceId})` : ''}`)
      }

      updateMessage(assistantId, { content: finalResponse } as Partial<Message>)

      const sessionsRes = await fetch('/api/sessions')
      const sessionsData = await sessionsRes.json()
      setSessions(Array.isArray(sessionsData) ? sessionsData : (sessionsData.sessions || []))
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      console.error('Chat error:', msg)
      updateMessage(assistantId, {
        role: 'system',
        content: `Chat failed: ${msg}\nCheck logs/features/chat_*.log and logs/agens_*.log`,
      } as Partial<Message>)
    } finally {
      setStreaming(false)
    }
  }

  const handleMouseDown = () => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const percentage = ((e.clientX - rect.left) / rect.width) * 100
      setSplitPosition(Math.max(30, Math.min(70, percentage)))
    }

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }

  return (
    <div className="flex flex-col h-full">
      <Header title="Chat" />

      <div className="flex-1 flex overflow-hidden">
        <div
          ref={containerRef}
          className="flex-1 flex"
          style={{ width: `${splitPosition}%` }}
        >
          <ChatWindow
            messages={messages}
            isStreaming={isStreaming}
            onSendMessage={handleSendMessage}
          />
        </div>

        <div
          className="w-1 bg-border hover:bg-primary cursor-col-resize transition-colors duration-200"
          onMouseDown={handleMouseDown}
        />

        <div
          className="overflow-hidden"
          style={{ width: `${100 - splitPosition}%` }}
        >
          <InvocationTrace events={traceEvents} isStreaming={isStreaming} />
        </div>
      </div>
    </div>
  )
}
