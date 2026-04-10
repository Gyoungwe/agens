import { useState, useRef, useEffect } from 'react'
import { Header } from '@/components/layout'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { AgentTopology } from '@/components/agent-graph/AgentTopology'
import { useChatStore, useAgentStore } from '@/store'

export function ChatPage() {
  const [splitPosition, setSplitPosition] = useState(60)
  const containerRef = useRef<HTMLDivElement>(null)
  const { messages, isStreaming, currentSessionId, setSessions, setCurrentSession, addMessage, setStreaming } = useChatStore()
  const { agents } = useAgentStore()

  useEffect(() => {
    fetch('/api/sessions')
      .then((res) => res.json())
      .then((data) => {
        setSessions(data.sessions || [])
        if (data.sessions?.length > 0) {
          setCurrentSession(data.sessions[0].session_id)
        }
      })
  }, [setSessions, setCurrentSession])

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user' as const,
      content: message,
      created_at: new Date().toISOString(),
      session_id: currentSessionId || undefined,
    }
    addMessage(userMessage)
    setStreaming(true)

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

      const reader = response.body?.getReader()
      if (!reader) return

      while (true) {
        const { done } = await reader.read()
        if (done) break
      }

      const sessionsRes = await fetch('/api/sessions')
      const sessionsData = await sessionsRes.json()
      setSessions(sessionsData.sessions || [])
    } catch (error) {
      console.error('Chat error:', error)
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
          className="w-1 bg-border hover:bg-primary cursor-col-resize transition-colors"
          onMouseDown={handleMouseDown}
        />

        <div
          className="overflow-hidden"
          style={{ width: `${100 - splitPosition}%` }}
        >
          <AgentTopology agents={agents} />
        </div>
      </div>
    </div>
  )
}
