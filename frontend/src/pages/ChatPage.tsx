import { useState, useRef, useEffect } from 'react'
import { Header } from '@/components/layout'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { InvocationTrace } from '@/components/chat/InvocationTrace'
import { useChatStore, useChatPreferencesStore } from '@/store'
import { parseSSEStream } from '@/utils/sse'
import type { Message } from '@/types'
import type { TraceEvent } from '@/components/chat/InvocationTrace'
import { providersApi } from '@/api/providers'
import { useNavigate } from 'react-router-dom'

export function ChatPage() {
  const navigate = useNavigate()
  const [splitPosition, setSplitPosition] = useState(60)
  const containerRef = useRef<HTMLDivElement>(null)
  const { messages, isStreaming, currentSessionId, setSessions, setCurrentSession, addMessage, updateMessage, setStreaming } = useChatStore()
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([])
  const [sessionTraceMap, setSessionTraceMap] = useState<Record<string, TraceEvent[]>>({})
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [providerInfo, setProviderInfo] = useState<{ id: string; name: string; model: string } | null>(null)
  const [pendingWorkflowTraceId, setPendingWorkflowTraceId] = useState<string | null>(null)
  const [pendingWorkflowFields, setPendingWorkflowFields] = useState<string[]>([])
  const [sessionList, setSessionList] = useState<Array<{ session_id: string; title?: string; updated_at?: string }>>([])
  const [streamStageLabel, setStreamStageLabel] = useState<string>('')
  const [userError, setUserError] = useState<string | null>(null)
  const [lastSentMessage, setLastSentMessage] = useState<string>('')
  const [mobileTraceOpen, setMobileTraceOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const { defaultChatMode, memoryScope, realtimeLogsEnabled } = useChatPreferencesStore()

  const classifyTaskType = (text: string): 'chat' | 'bio_workflow' | 'uncertain' => {
    const t = text.trim().toLowerCase()
    if (!t) return 'chat'

    const hardChatPatterns = [
      /生日|birthday|是谁|what is|who is|怎么说|翻译|解释|meaning|含义/,
      /你好|hi|hello|早上好|晚上好|谢谢|thank you/,
      /写一段|润色|改写|总结一下|随便聊聊|聊天/,
    ]
    if (hardChatPatterns.some((re) => re.test(t))) return 'chat'

    const bioWorkflowPatterns = [
      /rna-?seq|wgs|wes|metagenomics|atac-?seq|chip-?seq|assembly/,
      /fastq|bam|vcf|gtf|fasta|nextflow|snakemake|qc|quality control/,
      /生信|生物信息|pipeline|workflow|差异表达|变异检测|组装/,
      /样本|参考基因组|annotation|reference bundle/,
    ]
    if (bioWorkflowPatterns.some((re) => re.test(t))) return 'bio_workflow'

    return 'uncertain'
  }

  useEffect(() => {
    fetch('/api/sessions?kind=chat')
      .then((res) => res.json())
      .then((data) => {
        const sessions = Array.isArray(data) ? data : (data.sessions || [])
        setSessions(sessions)
        setSessionList(sessions)
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
    const update = () => setIsMobile(window.innerWidth < 768)
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
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
    setLastSentMessage(message)
    setUserError(null)
    setStreamStageLabel('Connecting...')
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
      const classified = defaultChatMode === 'auto' ? classifyTaskType(message) : defaultChatMode
      const effectiveMode = classified === 'uncertain' ? 'chat' : classified

      if (defaultChatMode === 'auto' && classified === 'uncertain') {
        addMessage({
          id: `system-clarify-${Date.now()}`,
          role: 'system',
          content: '我先按普通对话来回答；如果你想执行生信流程，请明确写出分析目标和数据类型（如 RNA-seq/FASTQ/QC）。',
          created_at: new Date().toISOString(),
          session_id: currentSessionId || undefined,
        })
      }
      const endpoint = effectiveMode === 'bio_workflow' ? '/api/bio/workflow?stream=true' : '/api/chat/stream'
      const body = effectiveMode === 'bio_workflow'
        ? {
            goal: message,
            dataset: 'chat-session',
            session_id: currentSessionId,
            continue_on_error: true,
            user_input_payload: pendingWorkflowTraceId
              ? {
                  user_answer: message,
                  provided_fields: pendingWorkflowFields,
                }
              : undefined,
            resume_from_trace_id: pendingWorkflowTraceId || undefined,
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

        if (effectiveMode === 'bio_workflow') {
          if (sseEvent.eventType === 'bio_stage_pending' || sseEvent.eventType === 'bio_stage_running' || sseEvent.eventType === 'bio_stage_done') {
            const stage = String(eventData.stage || 'unknown')
            stageStatus[stage] = {
              status: String(eventData.status || (sseEvent.eventType === 'bio_stage_running' ? 'running' : sseEvent.eventType === 'bio_stage_pending' ? 'pending' : 'done')),
              elapsed_ms: Number(eventData.elapsed_ms || 0),
              error: (eventData.error as string | null) || null,
            }
            setStreamStageLabel(`Workflow: ${toChineseStageName(stage)} ${toChineseStatus(stageStatus[stage].status)}`)
            updateMessage(assistantId, { content: renderBioProgress() } as Partial<Message>)
          } else if (sseEvent.eventType === 'bio_workflow_needs_input') {
            const q = String(eventData.user_question || 'Need more user input')
            const fields = Array.isArray(eventData.required_fields) ? (eventData.required_fields as string[]).join(', ') : ''
            setPendingWorkflowTraceId(String(eventData.trace_id || traceId || ''))
            setPendingWorkflowFields(Array.isArray(eventData.required_fields) ? (eventData.required_fields as string[]) : [])
            const progressText = Object.keys(stageStatus).length > 0 ? `${renderBioProgress()}\n\n` : ''
            finalResponse = `${progressText}流程已暂停：需要你补充信息后才能继续。\n\n问题：${q}${fields ? `\n建议补充字段：${fields}` : ''}`
          } else if (sseEvent.eventType === 'bio_workflow_final') {
            const workflowSummary = String(eventData.response || '')
            const status = String(eventData.status || 'unknown')
            const statusCn = status === 'success'
              ? '流程已成功完成'
              : status === 'needs_user_input'
                ? '流程暂停，等待你的输入'
                : '流程已结束，但有部分步骤失败'
            const progressText = Object.keys(stageStatus).length > 0 ? `${renderBioProgress()}\n\n` : ''
            finalResponse = `${progressText}最终结论：${statusCn}\n\n${workflowSummary || '系统已完成执行，但没有返回额外摘要。'}`
            setPendingWorkflowTraceId(null)
            setPendingWorkflowFields([])
            setStreamStageLabel('Workflow finalizing...')
          } else if (sseEvent.eventType === 'error') {
            throw new Error((eventData.message as string) || (eventData.error as string) || 'workflow stream error')
          }
        } else if (sseEvent.eventType === 'task_failed' || sseEvent.eventType === 'task_timeout') {
          const err = (eventData.error as string) || (eventData.message as string) || sseEvent.eventType
          throw new Error(`${sseEvent.eventType}: ${err}`)
        } else if (sseEvent.eventType === 'final_response') {
          finalResponse = ((eventData.data as Record<string, unknown>)?.response as string) || ''
          setStreamStageLabel('Synthesizing final response...')
        } else if (sseEvent.eventType === 'error') {
          throw new Error((eventData.message as string) || (eventData.error as string) || 'stream error')
        }
      }

      if (!finalResponse) {
        throw new Error(`No final_response received${traceId ? ` (trace_id=${traceId})` : ''}`)
      }

      updateMessage(assistantId, { content: finalResponse } as Partial<Message>)
      setSelectedImage(null)

      const sessionsRes = await fetch('/api/sessions?kind=chat')
      const sessionsData = await sessionsRes.json()
      const sessions = Array.isArray(sessionsData) ? sessionsData : (sessionsData.sessions || [])
      setSessions(sessions)
      setSessionList(sessions)
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      console.error('Chat error:', msg)
      setUserError(`Request failed: ${msg}`)
      updateMessage(assistantId, {
        role: 'system',
        content: `聊天失败：${msg}\n你可以点击 Retry Last 重试，或切换模型后再试。`,
      } as Partial<Message>)
    } finally {
      setStreamStageLabel('')
      setStreaming(false)
    }
  }

  const handleNewChat = async () => {
    try {
      const res = await fetch('/api/sessions?title=New%20Chat&kind=chat', {
        method: 'POST',
      })
      const data = await res.json()
      const newSessionId = data.session_id as string
      setCurrentSession(newSessionId)
      useChatStore.getState().setMessages([])
      setTraceEvents([])
      setSelectedImage(null)
      setPendingWorkflowTraceId(null)
      setPendingWorkflowFields([])

      const sessionsRes = await fetch('/api/sessions?kind=chat')
      const sessionsData = await sessionsRes.json()
      setSessions(Array.isArray(sessionsData) ? sessionsData : (sessionsData.sessions || []))
    } catch (e) {
      console.error('Failed to create new chat session', e)
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

      {userError && (
        <div className="mx-4 mt-3 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm flex items-center justify-between gap-3">
          <span>{userError}</span>
          <button
            onClick={() => {
              if (lastSentMessage) handleSendMessage(lastSentMessage)
            }}
            disabled={!lastSentMessage || isStreaming}
            className="px-3 py-1.5 text-xs rounded-lg border border-destructive/40 hover:bg-destructive/20 disabled:opacity-50"
          >
            Retry Last
          </button>
        </div>
      )}

      <div className="px-4 py-2 border-b border-border flex items-center gap-2 flex-wrap md:gap-2 overflow-x-auto">
        <button
          onClick={handleNewChat}
          className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
        >
          New Chat
        </button>
        <button
          onClick={() => navigate('/sessions')}
          className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
          title="Open full sessions history"
        >
          Sessions
        </button>
        <button
          onClick={() => setMobileTraceOpen((v) => !v)}
          className="md:hidden px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
          aria-expanded={mobileTraceOpen}
          aria-label="Toggle invocation trace panel"
        >
          Trace
        </button>
        <select
          value={currentSessionId || ''}
          onChange={(e) => setCurrentSession(e.target.value)}
          className="px-2 py-1.5 text-xs rounded-lg border border-border bg-background max-w-[280px]"
          title="历史会话"
        >
          {sessionList.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {(s.title && s.title.trim()) || s.session_id.slice(0, 8)}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        <div
          ref={containerRef}
          className="flex-none min-w-0 h-full"
          style={{ width: isMobile ? '100%' : `${splitPosition}%` }}
        >
          <ChatWindow
            messages={messages}
            isStreaming={isStreaming}
            streamStageLabel={streamStageLabel}
            onSendMessage={handleSendMessage}
            onSelectImage={setSelectedImage}
            selectedImage={selectedImage ? { name: selectedImage.name, size: selectedImage.size } : null}
          />
        </div>

        <div
          className="hidden md:block w-1 bg-border hover:bg-primary cursor-col-resize transition-colors duration-200"
          onMouseDown={handleMouseDown}
        />

        {realtimeLogsEnabled && (
          <div
            className={`${mobileTraceOpen ? 'block' : 'hidden'} md:block flex-none min-w-0 overflow-hidden border-t md:border-t-0 md:border-l border-border`}
            style={{ width: isMobile ? '100%' : `${100 - splitPosition}%` }}
          >
            <InvocationTrace events={traceEvents} isStreaming={isStreaming} />
          </div>
        )}
      </div>
    </div>
  )
}
