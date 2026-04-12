import { useState } from 'react'
import { Search, FlaskConical, Sparkles } from 'lucide-react'
import { researchApi } from '@/api/research'
import { parseSSEStream } from '@/utils/sse'

type SourceItem = {
  text: string
  type: 'website' | 'paper' | 'other'
  link?: string
}

type ParsedSection = {
  title: string
  items: string[]
}

const sectionPatterns: Array<{ key: string; title: string; pattern: RegExp }> = [
  { key: 'findings', title: 'Key Findings', pattern: /(关键发现|key findings?)/i },
  { key: 'evidence', title: 'Evidence & Sources', pattern: /(证据|来源|evidence|sources?)/i },
  { key: 'risks', title: 'Risks & Limits', pattern: /(风险|局限|risk|limit)/i },
  { key: 'next', title: 'Next Steps', pattern: /(下一步|建议|next steps?|recommend)/i },
]

function parseBullets(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => /^[-•*]\s+/.test(line) || /^\d+\.\s+/.test(line))
    .map((line) => line.replace(/^([-•*]|\d+\.)\s+/, '').trim())
    .filter(Boolean)
}

function parseStructuredSummary(summary: string): ParsedSection[] {
  const lines = summary.split(/\r?\n/)
  const sections: ParsedSection[] = []
  let current: ParsedSection | null = null

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) continue

    const matched = sectionPatterns.find((s) => s.pattern.test(line))
    if (matched) {
      current = { title: matched.title, items: [] }
      sections.push(current)
      continue
    }

    if (/^[-•*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      if (!current) {
        current = { title: 'Highlights', items: [] }
        sections.push(current)
      }
      current.items.push(line.replace(/^([-•*]|\d+\.)\s+/, '').trim())
    }
  }

  return sections.filter((s) => s.items.length > 0)
}

export function ResearchPage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ research: string; summary: string; session_id?: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [timeline, setTimeline] = useState<string[]>([])
  const [sources, setSources] = useState<SourceItem[]>([])
  const [knowledge, setKnowledge] = useState<string[]>([])

  const runResearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const { data } = await researchApi.run({ query: query.trim() })
      setResult({ research: data.research, summary: data.summary, session_id: data.session_id })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Research failed')
    } finally {
      setLoading(false)
    }
  }

  const runResearchStream = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setTimeline([])
    setSources([])
    setKnowledge([])

    try {
      const res = await researchApi.stream({ query: query.trim() })
      if (!res.body) throw new Error('No stream body received')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      for await (const sseEvent of parseSSEStream(reader, decoder)) {
        if (sseEvent.eventType === 'research_progress') {
          const msg = String(sseEvent.data.message || 'Research in progress...')
          setTimeline((prev) => [...prev, msg])
        } else if (sseEvent.eventType === 'research_source') {
          const src = String(sseEvent.data.source || '')
          const sourceType = (sseEvent.data.source_type as SourceItem['type'] | undefined) || 'other'
          const sourceLink = String(sseEvent.data.source_link || '')
          if (src) {
            setSources((prev) => {
              if (prev.some((p) => p.text === src)) return prev
              return [...prev, { text: src, type: sourceType, link: sourceLink || undefined }]
            })
          }
        } else if (sseEvent.eventType === 'research_knowledge') {
          const point = String(sseEvent.data.point || '')
          if (point) setKnowledge((prev) => (prev.includes(point) ? prev : [...prev, point]))
        } else if (sseEvent.eventType === 'research_done') {
          setResult({
            research: String(sseEvent.data.research || ''),
            summary: String(sseEvent.data.summary || ''),
            session_id: (sseEvent.data.session_id as string) || undefined,
          })
          const sourceItems = (sseEvent.data.source_items as SourceItem[] | undefined) || []
          setSources(sourceItems)
          setKnowledge((sseEvent.data.knowledge as string[] | undefined) || [])
          setTimeline((prev) => [...prev, 'Research completed.'])
        } else if (sseEvent.eventType === 'error') {
          throw new Error(String(sseEvent.data.message || 'Research stream failed'))
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Research streaming failed')
    } finally {
      setLoading(false)
    }
  }

  const evidenceChips = result ? parseBullets(result.research).slice(0, 12) : []
  const sections = result ? parseStructuredSummary(result.summary) : []

  return (
    <div className="h-full overflow-y-auto p-6 space-y-4">
      <div className="flex items-center gap-3">
        <FlaskConical className="w-6 h-6 text-primary" />
        <div>
          <h1 className="text-xl font-bold">Research Lab</h1>
          <p className="text-sm text-muted-foreground">Use research_agent + report synthesis for project investigation.</p>
        </div>
      </div>

      <div className="glass-card rounded-xl p-4 space-y-3">
        <label className="text-sm font-medium">Research query</label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full min-h-[90px] rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          placeholder="Describe what you want the bio research agent to investigate..."
        />
        <div className="flex items-center gap-2">
          <button
            onClick={runResearch}
            disabled={loading || !query.trim()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <Search className="w-4 h-4" />
            {loading ? 'Researching...' : 'Run Research'}
          </button>
          <button
            onClick={runResearchStream}
            disabled={loading || !query.trim()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-border bg-background hover:bg-muted/40 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <Sparkles className="w-4 h-4" />
            {loading ? 'Streaming...' : 'Stream Research'}
          </button>
        </div>
        {error && <div className="text-sm text-destructive">{error}</div>}
      </div>

      {(timeline.length > 0 || sources.length > 0 || knowledge.length > 0) && (
        <div className="glass-card rounded-xl p-4 space-y-3">
          <div className="text-sm font-medium">Live Research Timeline</div>
          {timeline.length > 0 && (
            <ul className="text-xs list-disc pl-4 space-y-1">
              {timeline.map((item, i) => <li key={`${item}-${i}`}>{item}</li>)}
            </ul>
          )}

          {sources.length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">Sources (Websites / Papers)</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="rounded-lg border border-border p-3 bg-muted/20">
                  <div className="text-xs font-medium mb-2">Websites</div>
                  <div className="space-y-2">
                    {sources.filter((s) => s.type === 'website').map((s, i) => (
                      <div key={`${s.text}-${i}`} className="text-xs break-all">
                        {s.link ? (
                          <a href={s.link} target="_blank" rel="noreferrer" className="text-primary underline">
                            {s.text}
                          </a>
                        ) : (
                          <span>{s.text}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-lg border border-border p-3 bg-muted/20">
                  <div className="text-xs font-medium mb-2">Papers</div>
                  <div className="space-y-2">
                    {sources.filter((s) => s.type === 'paper').map((s, i) => (
                      <div key={`${s.text}-${i}`} className="text-xs break-all">
                        {s.link ? (
                          <a href={s.link} target="_blank" rel="noreferrer" className="text-primary underline">
                            {s.text}
                          </a>
                        ) : (
                          <span>{s.text}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {knowledge.length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">Extracted Knowledge</div>
              <ul className="text-xs list-disc pl-4 space-y-1">
                {knowledge.map((k, i) => <li key={`${k}-${i}`}>{k}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="glass-card rounded-xl p-4">
            <div className="text-sm text-muted-foreground mb-2">Research Run</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="rounded-lg bg-muted/30 p-3">
                <div className="text-muted-foreground">Query</div>
                <div className="mt-1 font-medium break-words">{query}</div>
              </div>
              <div className="rounded-lg bg-muted/30 p-3">
                <div className="text-muted-foreground">Session</div>
                <div className="mt-1 font-medium">{result.session_id || 'N/A'}</div>
              </div>
              <div className="rounded-lg bg-muted/30 p-3">
                <div className="text-muted-foreground">Evidence Chips</div>
                <div className="mt-1 font-medium">{evidenceChips.length}</div>
              </div>
            </div>
          </div>

          {evidenceChips.length > 0 && (
            <div className="glass-card rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3 text-sm text-muted-foreground">
                <Search className="w-4 h-4" /> Evidence Chips
              </div>
              <div className="flex flex-wrap gap-2">
                {evidenceChips.map((chip, idx) => (
                  <span key={`${chip}-${idx}`} className="text-xs px-2.5 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
                    {chip}
                  </span>
                ))}
              </div>
            </div>
          )}

          {sections.length > 0 && (
            <div className="glass-card rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3 text-sm text-muted-foreground">
                <Sparkles className="w-4 h-4" /> Summary Timeline
              </div>
              <div className="space-y-3">
                {sections.map((section, idx) => (
                  <div key={`${section.title}-${idx}`} className="rounded-lg border border-border p-3 bg-muted/20">
                    <div className="text-sm font-semibold mb-2">{idx + 1}. {section.title}</div>
                    <ul className="text-xs space-y-1 list-disc pl-4">
                      {section.items.map((item, i) => (
                        <li key={`${item}-${i}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2 text-sm text-muted-foreground">
              <Search className="w-4 h-4" /> Raw Findings
            </div>
            <pre className="text-xs whitespace-pre-wrap bg-muted/30 rounded-lg p-3 max-h-[420px] overflow-y-auto">
              {result.research}
            </pre>
          </div>
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2 text-sm text-muted-foreground">
              <Sparkles className="w-4 h-4" /> Structured Summary
            </div>
            <pre className="text-xs whitespace-pre-wrap bg-muted/30 rounded-lg p-3 max-h-[420px] overflow-y-auto">
              {result.summary}
            </pre>
          </div>
        </div>
        </div>
      )}
    </div>
  )
}
