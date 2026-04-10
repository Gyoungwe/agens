import { useCallback, useRef, useEffect } from 'react'
import { useChatStore } from '@/store'

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null)
  const { setStreaming, addMessage } = useChatStore()

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

      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += new TextDecoder().decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))

                if (data.type === 'start') {
                  addMessage({
                    id: data.message_id,
                    role: 'assistant',
                    content: '',
                    created_at: new Date().toISOString(),
                    session_id: sessionId,
                  })
                } else if (data.type === 'chunk') {
                  // Content is streamed incrementally
                } else if (data.type === 'done') {
                  setStreaming(false)
                }
              } catch {
                // Ignore parse errors for incomplete JSON
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
        setStreaming(false)
      }
    },
    [setStreaming, addMessage]
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
