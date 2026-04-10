import { useCallback, useRef, useEffect } from 'react'
import { useChatStore } from '@/store'
import { parseSSEStream } from '@/utils/sse'

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null)
  const { setStreaming, addMessage, updateMessage } = useChatStore()

  const sendMessage = useCallback(
    async (message: string, sessionId?: string) => {
      setStreaming(true)

      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({ message, session_id: sessionId }),
      })

      const reader = response.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let currentMessageId: string | null = null

      try {
        for await (const sseEvent of parseSSEStream(reader, decoder)) {
          if (sseEvent.eventType === 'start') {
            const msgId = sseEvent.data.message_id as string
            currentMessageId = msgId
            addMessage({
              id: msgId,
              role: 'assistant',
              content: '',
              created_at: new Date().toISOString(),
              session_id: sessionId,
            })
          } else if (sseEvent.eventType === 'chunk') {
            const content = (sseEvent.data.content as string) || ''
            if (currentMessageId && content) {
              updateMessage(currentMessageId, { content } as Partial<import('@/types').Message>)
            }
          } else if (sseEvent.eventType === 'done') {
            setStreaming(false)
            break
          }
        }
      } finally {
        reader.releaseLock()
        setStreaming(false)
      }
    },
    [setStreaming, addMessage, updateMessage]
  )

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return { sendMessage, disconnect }
}
