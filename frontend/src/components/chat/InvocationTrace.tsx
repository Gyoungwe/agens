import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, Bot, Sparkles, FileText, CheckCircle, XCircle, Clock } from 'lucide-react'

export interface TraceEvent {
  event_id: string
  type: string
  agent: string
  status: string
  data: Record<string, unknown>
  created_at: number
}

interface InvocationTraceProps {
  events: TraceEvent[]
  isStreaming: boolean
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  agent_start: <Bot size={14} className="text-blue-500" />,
  agent_thinking: <Sparkles size={14} className="text-yellow-500" />,
  agent_tool_call: <Sparkles size={14} className="text-purple-500" />,
  agent_file_read: <FileText size={14} className="text-green-500" />,
  agent_output: <FileText size={14} className="text-cyan-500" />,
  agent_done: <CheckCircle size={14} className="text-green-600" />,
  final_response: <CheckCircle size={14} className="text-green-600" />,
  task_failed: <XCircle size={14} className="text-red-500" />,
  task_timeout: <Clock size={14} className="text-orange-500" />,
  error: <XCircle size={14} className="text-red-500" />,
}

const EVENT_COLORS: Record<string, string> = {
  agent_start: 'border-l-blue-500 bg-blue-50/30',
  agent_thinking: 'border-l-yellow-500 bg-yellow-50/30',
  agent_tool_call: 'border-l-purple-500 bg-purple-50/30',
  agent_file_read: 'border-l-green-500 bg-green-50/30',
  agent_output: 'border-l-cyan-500 bg-cyan-50/30',
  agent_done: 'border-l-green-600 bg-green-50/30',
  final_response: 'border-l-green-600 bg-green-50/30',
  task_failed: 'border-l-red-500 bg-red-50/30',
  task_timeout: 'border-l-orange-500 bg-orange-50/30',
  error: 'border-l-red-500 bg-red-50/30',
}

const EVENT_LABELS: Record<string, string> = {
  agent_start: 'Agent Started',
  agent_thinking: 'Thinking',
  agent_tool_call: 'Tool Call',
  agent_file_read: 'File Read',
  agent_output: 'Output',
  agent_done: 'Agent Done',
  final_response: 'Final Response',
  task_failed: 'Task Failed',
  task_timeout: 'Timeout',
  error: 'Error',
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('en-US', { hour12: false })
}

function formatDuration(start: number, end: number): string {
  const ms = Math.round((end - start) * 1000)
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function TraceItem({ event, prevEvent }: { event: TraceEvent; prevEvent?: TraceEvent }) {
  const [expanded, setExpanded] = useState(false)
  const icon = EVENT_ICONS[event.type] || <Sparkles size={14} className="text-gray-500" />
  const colorClass = EVENT_COLORS[event.type] || 'border-l-gray-400 bg-gray-50/30'
  const label = EVENT_LABELS[event.type] || event.type
  const duration = prevEvent ? formatDuration(prevEvent.created_at, event.created_at) : null

  const renderContent = () => {
    const data = event.data || {}
    switch (event.type) {
      case 'agent_thinking':
        return <span className="text-yellow-700">{String(data.message || '')}</span>
      case 'agent_tool_call':
        return <span className="text-purple-700">Calling {String(data.skill_id || data.tool || 'tool')}...</span>
      case 'agent_file_read':
        return <span className="text-green-700">{String(data.file_path || '')}</span>
      case 'agent_output':
        return <span className="text-cyan-700 truncate block max-w-xs">{String(data.summary || data.output || '')}</span>
      case 'agent_done':
        return <span className="text-green-700 truncate block max-w-xs">{String(data.result || '')}</span>
      case 'final_response':
        return <span className="text-green-700 truncate block max-w-xs">{String(data.response || '')}</span>
      case 'task_failed':
      case 'error':
        return <span className="text-red-700">{String(data.error || '')}</span>
      case 'task_timeout':
        return <span className="text-orange-700">Timeout after {String(data.timeout_seconds ?? '')}s</span>
      default:
        return null
    }
  }

  return (
    <div
      className={`border-l-2 ${colorClass} pl-3 py-1.5 rounded-r pr-2 mb-1 transition-all hover:shadow-sm`}
    >
      <div className="flex items-center gap-2 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        {expanded ? <ChevronDown size={12} className="text-gray-400" /> : <ChevronRight size={12} className="text-gray-400" />}
        {icon}
        <span className="text-xs font-medium text-gray-700">{label}</span>
        <span className="text-xs text-gray-400">@{event.agent || 'system'}</span>
        <span className="text-xs text-gray-400 ml-auto">{formatTime(event.created_at)}</span>
        {duration && <span className="text-xs text-gray-400">({duration})</span>}
      </div>
      {expanded && (
        <div className="mt-1 pl-5 text-xs text-gray-600 break-all">
          {renderContent()}
          {Object.keys(event.data || {}).length > 0 && (
            <pre className="mt-1 p-1 bg-gray-100 rounded text-xs overflow-auto max-h-32">
              {JSON.stringify(event.data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

export function InvocationTrace({ events, isStreaming }: InvocationTraceProps) {
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll) {
      const container = document.getElementById('trace-container')
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    }
  }, [events, autoScroll])

  const agentStats = events.reduce((acc, e) => {
    if (e.agent) {
      acc[e.agent] = acc[e.agent] || { start: e.created_at, end: e.created_at, count: 0 }
      acc[e.agent].end = e.created_at
      acc[e.agent].count++
    }
    return acc
  }, {} as Record<string, { start: number; end: number; count: number }>)

  return (
    <div className="h-full flex flex-col bg-background border-l">
      <div className="px-3 py-2 border-b bg-muted/30">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">Invocation Trace</h3>
          <div className="flex items-center gap-2">
            {isStreaming && (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                Streaming
              </span>
            )}
            <span className="text-xs text-muted-foreground">{events.length} events</span>
          </div>
        </div>

        {Object.keys(agentStats).length > 0 && (
          <div className="flex gap-2 mt-2 flex-wrap">
            {Object.entries(agentStats).map(([agent, stats]) => (
              <div key={agent} className="flex items-center gap-1 text-xs bg-muted px-2 py-0.5 rounded">
                <Bot size={10} />
                <span className="font-medium">{agent}</span>
                <span className="text-muted-foreground">
                  {formatDuration(stats.start, stats.end)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div
        id="trace-container"
        className="flex-1 overflow-y-auto p-2"
        onScroll={(e) => {
          const target = e.currentTarget
          const atBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 50
          setAutoScroll(atBottom)
        }}
      >
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <Bot size={32} className="mb-2 opacity-20" />
            <p className="text-sm">Send a message to see the invocation trace</p>
          </div>
        ) : (
          events.map((event, index) => (
            <TraceItem
              key={event.event_id}
              event={event}
              prevEvent={index > 0 ? events[index - 1] : undefined}
            />
          ))
        )}
      </div>

      <div className="px-3 py-1.5 border-t bg-muted/20 flex items-center justify-between">
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="w-3 h-3"
          />
          Auto-scroll
        </label>
      </div>
    </div>
  )
}
