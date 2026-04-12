import { MarkdownBlock } from '@/components/shared/MarkdownBlock'

interface RichAgentOutputProps {
  content: string
  isUser: boolean
}

function classifyLine(line: string): 'heading' | 'bullet' | 'stage' | 'summary' | 'plain' {
  const trimmed = line.trim()
  if (!trimmed) return 'plain'
  if (trimmed.startsWith('## ') || trimmed.startsWith('# ')) return 'heading'
  if (trimmed.startsWith('- ')) {
    if (trimmed.includes('：等待中') || trimmed.includes('：进行中') || trimmed.includes('：已完成') || trimmed.includes('：失败') || trimmed.includes('：超时')) {
      return 'stage'
    }
    return 'bullet'
  }
  if (trimmed.startsWith('最终结论：') || trimmed.startsWith('Final Status:')) return 'summary'
  return 'plain'
}

export function RichAgentOutput({ content, isUser }: RichAgentOutputProps) {
  if (isUser) {
    return <MarkdownBlock content={content} className="prose-p:my-1" />
  }

  const lines = content.split('\n')
  const hasStructured = lines.some((line) => {
    const c = classifyLine(line)
    return c === 'heading' || c === 'stage' || c === 'summary'
  })

  if (!hasStructured) {
    return <MarkdownBlock content={content} />
  }

  return (
    <div className="space-y-2">
      {lines.map((line, idx) => {
        const type = classifyLine(line)
        const text = line.replace(/^[-#\s]+/, '')

        if (!line.trim()) {
          return <div key={idx} className="h-1" />
        }

        if (type === 'heading') {
          return (
            <div key={idx} className="text-sm font-semibold text-foreground border-l-2 border-primary/60 pl-2">
              {text}
            </div>
          )
        }

        if (type === 'summary') {
          return (
            <div key={idx} className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium">
              {line}
            </div>
          )
        }

        if (type === 'stage') {
          const status = line.includes('已完成')
            ? 'done'
            : line.includes('进行中')
              ? 'running'
              : line.includes('等待中')
                ? 'pending'
                : line.includes('失败') || line.includes('超时')
                  ? 'error'
                  : 'unknown'

          const chipClass =
            status === 'done'
              ? 'bg-emerald-500/10 text-emerald-700 border-emerald-500/30'
              : status === 'running'
                ? 'bg-blue-500/10 text-blue-700 border-blue-500/30'
                : status === 'pending'
                  ? 'bg-amber-500/10 text-amber-700 border-amber-500/30'
                  : status === 'error'
                    ? 'bg-rose-500/10 text-rose-700 border-rose-500/30'
                    : 'bg-muted text-muted-foreground border-border'

          return (
            <div key={idx} className="rounded-lg border border-border/70 bg-muted/20 px-3 py-2 text-sm flex items-start justify-between gap-3">
              <span className="leading-relaxed">{text}</span>
              <span className={`text-[10px] font-semibold uppercase tracking-wide rounded-full border px-2 py-0.5 ${chipClass}`}>
                {status}
              </span>
            </div>
          )
        }

        if (type === 'bullet') {
          return (
            <div key={idx} className="text-sm text-foreground/90 pl-4 relative leading-relaxed">
              <span className="absolute left-0 top-2 w-1.5 h-1.5 rounded-full bg-primary/70" />
              {text}
            </div>
          )
        }

        return (
          <div key={idx} className="text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap break-words">
            {line}
          </div>
        )
      })}
    </div>
  )
}
