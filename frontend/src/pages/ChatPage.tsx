import { useState, useRef, useEffect } from 'react'
import { Header } from '@/components/layout'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { InvocationTrace } from '@/components/chat/InvocationTrace'
import { useChatStore } from '@/store'
import { parseSSEStream } from '@/utils/sse'
import type { Message } from '@/types'
import type { TraceEvent } from '@/components/chat/InvocationTrace'
import { providersApi } from '@/api/providers'

export function ChatPage() {
  const [splitPosition, setSplitPosition] = useState(60)
  const [chatMode, setChatMode] = useState<'chat' | 'bio_workflow'>('chat')
  const containerRef = useRef<HTMLDivElement>(null)
  const { messages, isStreaming, currentSessionId, setSessions, setCurrentSession, addMessage, updateMessage, setStreaming } = useChatStore()
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([])
  const [sessionTraceMap, setSessionTraceMap] = useState<Record<string, TraceEvent[]>>({})
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [providerInfo, setProviderInfo] = useState<{ id: string; name: string; model: string } | null>(null)
  const [memoryScope, setMemoryScope] = useState<'session' | 'global'>('session')

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

  useEffect(() => {
    providersApi.getCurrentProvider()
      .then((res) => setProviderInfo(res.data))
      .catch(() => setProviderInfo(null))
  }, [])

  useEffect(() => {
    if (!currentSessionId) return
    setTraceEvents(sessionTraceMap[currentSessionId] || [])
  }, [currentSessionId, sessionTraceMap])

  useEffect(() => {
    if (!currentSessionId) return
    fetch(`/api/chat/history/${currentSessionId}`)
      .then((res) => res.json())
      .then((data) => {
        const raw = Array.isArray(data?.messages) ? data.messages : []
        const mapped: Message[] = raw.map((m: unknown, idx: number) => {
          const item = (m && typeof m === 'object') ? (m as Record<string, unknown>) : {}
          const roleRaw = String(item.role || 'assistant')
          const role: Message['role'] = roleRaw === 'user' || roleRaw === 'system' ? roleRaw : 'assistant'
          return {
            id: String(item.id || `msg-${idx}-${Date.now()}`),
            role,
            content: String(item.content || ''),
            created_at: String(item.created_at || new Date().toISOString()),
            session_id: currentSessionId,
          }
        })
        useChatStore.getState().setMessages(mapped)
      })
      .catch(() => {
        useChatStore.getState().setMessages([])
      })
  }, [currentSessionId])

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return

    if (selectedImage) {
      const modelText = `${providerInfo?.id || ''} ${providerInfo?.name || ''} ${providerInfo?.model || ''}`.toLowerCase()
      const supportsVision =
        modelText.includes('gpt-4o') ||
        modelText.includes('vision') ||
        modelText.includes('claude-3') ||
        modelText.includes('sonnet')

      if (!supportsVision) {
        addMessage({
          id: `system-${Date.now()}`,
          role: 'system',
          content: `当前模型（${providerInfo?.model || providerInfo?.id || 'unknown'}）不支持图片输入。请切换到支持视觉的模型（如 GPT-4o / Claude 3.x）后再发送图片。`,
          created_at: new Date().toISOString(),
          session_id: currentSessionId || undefined,
        })
        return
      }
    }

    // Keep invocation trace continuity within the same session

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
      const endpoint = chatMode === 'bio_workflow' ? '/api/bio/workflow?stream=true' : '/api/chat/stream'
      const body = chatMode === 'bio_workflow'
        ? {
            goal: message,
            dataset: 'chat-session',
            session_id: currentSessionId,
            continue_on_error: true,
          }
        : {
            message: selectedImage ? `${message}\n\n[image_attached:${selectedImage.name}]` : message,
            session_id: currentSessionId,
            memory_scope: memoryScope,
          }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify(body),
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
      const stageStatus: Record<string, { status: string; elapsed_ms?: number; error?: string | null }> = {}

      const toChineseStageName = (stage: string): string => {
        const map: Record<string, string> = {
          planning: '规划',
          codegen: '代码生成',
          qc: '质控检查',
          report: '结果报告',
          evolution: '策略进化',
        }
        return map[stage] || stage
      }

      const toChineseStatus = (status: string): string => {
        if (status === 'pending') return '等待中'
        if (status === 'running') return '进行中'
        if (status === 'ok' || status === 'success' || status === 'done') return '已完成'
        if (status === 'timeout') return '超时'
        if (status === 'error' || status === 'failed') return '失败'
        return status
      }

      const renderBioProgress = (): string => {
        const lines = ['正在执行生物信息学流程，当前进展如下：']
        for (const [stage, info] of Object.entries(stageStatus)) {
          const elapsed = typeof info.elapsed_ms === 'number' && info.elapsed_ms > 0
            ? `，耗时约 ${(info.elapsed_ms / 1000).toFixed(1)} 秒`
            : ''
          const err = info.error ? `。异常原因：${info.error}` : ''
          lines.push(`- ${toChineseStageName(stage)}：${toChineseStatus(info.status)}${elapsed}${err}`)
        }
        lines.push('\n系统会继续推进后续步骤，直到完成或需要你补充信息。')
        return lines.join('\n')
      }

      for await (const sseEvent of parseSSEStream(reader, decoder)) {
        traceId = (sseEvent.data.trace_id as string) || traceId

        const eventData = sseEvent.data as Record<string, unknown>
        const traceEvent: TraceEvent = {
          event_id: String(sseEvent.eventType) + '-' + Date.now() + '-' + Math.random(),
          type: sseEvent.eventType,
          agent: String(eventData.agent || ''),
          status: String(eventData.status || 'running'),
          data: eventData,
          created_at: Date.now() / 1000,
        }
        setTraceEvents((prev) => [...prev, traceEvent])
        const sid = String(eventData.session_id || currentSessionId || 'pending')
        setSessionTraceMap((prev) => ({
          ...prev,
          [sid]: [...(prev[sid] || []), traceEvent],
        }))

        if (chatMode === 'bio_workflow') {
          if (sseEvent.eventType === 'bio_stage_pending' || sseEvent.eventType === 'bio_stage_running' || sseEvent.eventType === 'bio_stage_done') {
            const stage = String(eventData.stage || 'unknown')
            stageStatus[stage] = {
              status: String(eventData.status || (sseEvent.eventType === 'bio_stage_running' ? 'running' : sseEvent.eventType === 'bio_stage_pending' ? 'pending' : 'done')),
              elapsed_ms: Number(eventData.elapsed_ms || 0),
              error: (eventData.error as string | null) || null,
            }
            updateMessage(assistantId, { content: renderBioProgress() } as Partial<Message>)
          } else if (sseEvent.eventType === 'bio_workflow_needs_input') {
            const q = String(eventData.user_question || 'Need more user input')
            const fields = Array.isArray(eventData.required_fields) ? (eventData.required_fields as string[]).join(', ') : ''
            finalResponse = `${renderBioProgress()}\n\n流程已暂停：需要你补充信息后才能继续。\n\n问题：${q}${fields ? `\n建议补充字段：${fields}` : ''}`
          } else if (sseEvent.eventType === 'bio_workflow_final') {
            const workflowSummary = String(eventData.response || '')
            const status = String(eventData.status || 'unknown')
            const statusCn = status === 'success'
              ? '流程已成功完成'
              : status === 'needs_user_input'
                ? '流程暂停，等待你的输入'
                : '流程已结束，但有部分步骤失败'
            finalResponse = `${renderBioProgress()}\n\n最终结论：${statusCn}\n\n${workflowSummary || '系统已完成执行，但没有返回额外摘要。'}`
          } else if (sseEvent.eventType === 'error') {
            throw new Error((eventData.message as string) || (eventData.error as string) || 'workflow stream error')
          }
        } else if (sseEvent.eventType === 'task_failed' || sseEvent.eventType === 'task_timeout') {
          const err = (eventData.error as string) || (eventData.message as string) || sseEvent.eventType
          throw new Error(`${sseEvent.eventType}: ${err}`)
        } else if (sseEvent.eventType === 'final_response') {
          finalResponse = ((eventData.data as Record<string, unknown>)?.response as string) || ''
        } else if (sseEvent.eventType === 'error') {
          throw new Error((eventData.message as string) || (eventData.error as string) || 'stream error')
        }
      }

      if (!finalResponse) {
        throw new Error(`No final_response received${traceId ? ` (trace_id=${traceId})` : ''}`)
      }

      updateMessage(assistantId, { content: finalResponse } as Partial<Message>)
      setSelectedImage(null)

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

  const handleNewChat = async () => {
    try {
      const res = await fetch('/api/sessions?title=New%20Chat', {
        method: 'POST',
      })
      const data = await res.json()
      const newSessionId = data.session_id as string
      setCurrentSession(newSessionId)
      useChatStore.getState().setMessages([])
      setTraceEvents([])
      setSelectedImage(null)

      const sessionsRes = await fetch('/api/sessions')
      const sessionsData = await sessionsRes.json()
      setSessions(Array.isArray(sessionsData) ? sessionsData : (sessionsData.sessions || []))
    } catch (e) {
      console.error('Failed to create new chat session', e)
    }
  }

  const runMemorySelfCheck = () => {
    const checklist = [
      '记忆自检步骤：',
      '1) 在同一会话连续发送两条消息（包含可识别事实，如“我的项目代号是 A1”）。',
      '2) 发送“请复述我刚才给出的项目代号”。',
      '3) 切换新会话后再次询问，模型不应继续记住上一会话事实。',
      '4) 如需底层验证：访问 /debug/results/{session_id} 查看 task_results。',
    ].join('\n')
    addMessage({
      id: `system-memory-check-${Date.now()}`,
      role: 'system',
      content: checklist,
      created_at: new Date().toISOString(),
      session_id: currentSessionId || undefined,
    })
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

      <div className="px-4 py-2 border-b border-border flex items-center gap-2">
        <button
          onClick={handleNewChat}
          className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
        >
          New Chat
        </button>
        <button
          onClick={runMemorySelfCheck}
          className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
        >
          Memory Self-Check
        </button>
        <button
          onClick={() => setMemoryScope(memoryScope === 'session' ? 'global' : 'session')}
          className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
          title="Toggle memory retrieval scope"
        >
          Memory: {memoryScope === 'global' ? 'Global' : 'Session'}
        </button>
        <button
          onClick={() => setChatMode('chat')}
          className={`px-3 py-1.5 text-xs rounded-lg border ${chatMode === 'chat' ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted/50'}`}
        >
          Normal Chat
        </button>
        <button
          onClick={() => setChatMode('bio_workflow')}
          className={`px-3 py-1.5 text-xs rounded-lg border ${chatMode === 'bio_workflow' ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted/50'}`}
        >
          Bio Workflow Mode
        </button>
      </div>

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
            onSelectImage={setSelectedImage}
            selectedImage={selectedImage ? { name: selectedImage.name, size: selectedImage.size } : null}
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
