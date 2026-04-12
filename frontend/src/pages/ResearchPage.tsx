import { useEffect, useRef, useState } from 'react'
import { Search, FlaskConical, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { researchApi } from '@/api/research'
import { parseSSEStream } from '@/utils/sse'
import { MarkdownBlock } from '@/components/shared'
import { researchHistoryApi } from '@/api/researchHistory'
import type { Session } from '@/types'

type SourceItem = {
  text: string
  type: 'website' | 'paper' | 'other'
  link?: string
}

type ParsedSection = {
  title: string
  items: string[]
}

type JsonSummarySection = {
  heading?: string
  key_points?: unknown
  caveat?: unknown
}

type JsonSummaryPayload = {
  title?: unknown
  workflow_family?: unknown
  sections?: JsonSummarySection[]
  reproducibility_summary?: unknown
  limitations?: unknown
  next_steps?: unknown
  nextSteps?: unknown
  executive_summary?: unknown
  key_findings?: unknown
  findings?: unknown
  quality_assessment?: unknown
}

const sectionPatterns: Array<{ key: string; title: string; pattern: RegExp }> = [
  { key: 'findings', title: 'Key Findings', pattern: /(关键发现|key findings?)/i },
  { key: 'evidence', title: 'Evidence & Sources', pattern: /(证据|来源|evidence|sources?)/i },
  { key: 'risks', title: 'Risks & Limits', pattern: /(风险|局限|risk|limit)/i },
  { key: 'next', title: 'Next Steps', pattern: /(下一步|建议|next steps?|recommend)/i },
]

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

function extractUrlCitations(text: string): SourceItem[] {
  const regex = /https?:\/\/[\w.-]+(?:\/[\w\-./?%&=+#:]*)?/gi
  const urls = text.match(regex) || []
  const seen = new Set<string>()
  const out: SourceItem[] = []

  for (const u of urls) {
    const link = u.trim()
    if (!link || seen.has(link)) continue
    seen.add(link)
    const lower = link.toLowerCase()
    const type: SourceItem['type'] = /arxiv|pubmed|doi\.org|nature\.com|science\.org|sciencedirect/.test(lower) ? 'paper' : 'website'
    out.push({ text: link, type, link })
  }

  return out
}

// Attempt to parse a JSON payload embedded in the summary string.
// If the string is valid JSON object, return it; otherwise null.
function tryParseJsonPayload(text: string): JsonSummaryPayload | null {
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object') return parsed
  } catch {
    // not JSON
  }
  return null
}

function toStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function findJsonSection(payload: JsonSummaryPayload | null, heading: string): JsonSummarySection | null {
  if (!payload?.sections) return null
  return payload.sections.find((section) => String(section.heading || '').toLowerCase() === heading) || null
}

function prettyHeading(heading: string): string {
  const map: Record<string, string> = {
    executive_summary: 'Executive Summary',
    key_findings: 'Key Findings',
    quality_assessment: 'Quality Assessment',
    limitations: 'Limitations',
    next_steps: 'Next Steps',
  }
  return map[heading] || heading.replace(/_/g, ' ')
}

function hasCaveat(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function ResearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ research: string; summary: string; session_id?: string; summary_format?: 'text' | 'json' } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [timeline, setTimeline] = useState<string[]>([])
  const [sources, setSources] = useState<SourceItem[]>([])
  const [knowledge, setKnowledge] = useState<string[]>([])
  const [historySessions, setHistorySessions] = useState<Session[]>([])
  const [selectedHistorySession, setSelectedHistorySession] = useState<string>('')
  const [historyResults, setHistoryResults] = useState<Array<{ agent_id: string; result: string; created_at: string }>>([])
  const [historyQuery, setHistoryQuery] = useState('')
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [deletingHistory, setDeletingHistory] = useState(false)
  const [streamStage, setStreamStage] = useState<'idle' | 'searching' | 'analyzing' | 'summarizing' | 'done'>('idle')
  const streamAbortRef = useRef<AbortController | null>(null)

  const loadHistorySessions = async () => {
    try {
      setHistoryError(null)
      const { data } = await researchHistoryApi.listSessions()
      const sessions = (Array.isArray(data) ? data : []).slice().sort((a, b) => {
        const ta = new Date(a.updated_at || a.created_at || 0).getTime()
        const tb = new Date(b.updated_at || b.created_at || 0).getTime()
        return tb - ta
      })
      setHistorySessions(sessions)
      if (!selectedHistorySession && sessions.length > 0) {
        setSelectedHistorySession(sessions[0].session_id)
      }
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : 'Failed to load history sessions')
      setHistorySessions([])
    }
  }

  const loadHistoryDetail = async (sessionId: string) => {
    if (!sessionId) return
    try {
      setHistoryError(null)
      const historyRes = await researchHistoryApi.getResearchHistory(sessionId)
      const rows = Array.isArray(historyRes.data.results) ? historyRes.data.results : []
      const mapped = rows
        .map((r) => ({
          agent_id: r.agent_id,
          result: String(r.result || ''),
          created_at: r.created_at,
        }))
        .filter((x) => x.result)
      setHistoryResults(mapped)
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : 'Failed to load history detail')
      setHistoryResults([])
    }
  }

  const runResearch = async () => {
    if (!query.trim()) return
    streamAbortRef.current?.abort()
    setLoading(true)
    setError(null)
    setStreamStage('searching')
    try {
      const { data } = await researchApi.run({ query: query.trim() })
      setResult({ research: data.research, summary: data.summary, session_id: data.session_id, summary_format: data.summary_format })
      setStreamStage('done')
      await loadHistorySessions()
    } catch (e: unknown) {
      setStreamStage('idle')
      setError(e instanceof Error ? e.message : 'Research failed')
    } finally {
      setLoading(false)
    }
  }

  const runResearchStream = async () => {
    if (!query.trim()) return
    streamAbortRef.current?.abort()
    streamAbortRef.current = new AbortController()
    setLoading(true)
    setError(null)
    setTimeline([])
    setSources([])
    setKnowledge([])
    setStreamStage('searching')

    try {
      const res = await researchApi.stream({ query: query.trim(), signal: streamAbortRef.current.signal })
      if (!res.body) throw new Error('No stream body received')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      for await (const sseEvent of parseSSEStream(reader, decoder)) {
        if (sseEvent.eventType === 'research_progress') {
          const msg = String(sseEvent.data.message || 'Research in progress...')
          if ((sseEvent.data.stage as string) === 'summarizing') {
            setStreamStage('summarizing')
          } else {
            setStreamStage('analyzing')
          }
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
            summary_format: (sseEvent.data.summary_format as 'text' | 'json' | undefined) || undefined,
          })
          const sourceItems = (sseEvent.data.source_items as SourceItem[] | undefined) || []
          setSources(sourceItems)
          setKnowledge((sseEvent.data.knowledge as string[] | undefined) || [])
          setTimeline((prev) => [...prev, 'Research completed.'])
          setStreamStage('done')
          await loadHistorySessions()
        } else if (sseEvent.eventType === 'error') {
          throw new Error(String(sseEvent.data.message || 'Research stream failed'))
        }
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        setTimeline((prev) => [...prev, 'Previous stream cancelled.'])
      } else {
        setError(e instanceof Error ? e.message : 'Research streaming failed')
      }
      setStreamStage('idle')
    } finally {
      setLoading(false)
    }
  }

  const deleteSelectedHistory = async () => {
    if (!selectedHistorySession) return
    const target = historySessions.find((s) => s.session_id === selectedHistorySession)
    const label = (target?.title && target.title.trim()) || selectedHistorySession.slice(0, 8)
    const confirmed = window.confirm(`Delete research history session "${label}"? This cannot be undone.`)
    if (!confirmed) return

    setDeletingHistory(true)
    try {
      await researchHistoryApi.deleteResearchSession(selectedHistorySession)
      const nextSessions = historySessions.filter((s) => s.session_id !== selectedHistorySession)
      setHistorySessions(nextSessions)
      const nextId = nextSessions[0]?.session_id || ''
      setSelectedHistorySession(nextId)
      if (nextId) {
        await loadHistoryDetail(nextId)
      } else {
        setHistoryResults([])
      }
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : 'Failed to delete research history session')
    } finally {
      setDeletingHistory(false)
    }
  }

  // If the summary payload is a JSON object, render structured UI for it
  const jsonSummaryPayload = result?.summary_format === 'text' ? null : (result?.summary ? tryParseJsonPayload(result.summary) : null)
  const sections = result ? parseStructuredSummary(result.summary) : []
  const citationItems = result
    ? (sources.length > 0 ? sources : extractUrlCitations(`${result.summary}\n${result.research}`))
    : []
  const executiveSection = findJsonSection(jsonSummaryPayload, 'executive_summary')
  const findingsSection = findJsonSection(jsonSummaryPayload, 'key_findings')
  const qualitySection = findJsonSection(jsonSummaryPayload, 'quality_assessment')
  const limitationsSection = findJsonSection(jsonSummaryPayload, 'limitations')
  const nextStepsSection = findJsonSection(jsonSummaryPayload, 'next_steps')
  const structuredFindings = [
    ...toStringList(jsonSummaryPayload?.key_findings ?? jsonSummaryPayload?.findings),
    ...toStringList(findingsSection?.key_points),
  ]
  const structuredQuality = toStringList(qualitySection?.key_points ?? jsonSummaryPayload?.quality_assessment)
  const structuredLimitations = [
    ...toStringList(jsonSummaryPayload?.limitations),
    ...toStringList(limitationsSection?.key_points),
  ]
  const structuredNextSteps = [
    ...toStringList(jsonSummaryPayload?.next_steps ?? jsonSummaryPayload?.nextSteps),
    ...toStringList(nextStepsSection?.key_points),
  ]
  const evidenceItems = [...structuredFindings, ...structuredQuality]
  const filteredHistorySessions = historySessions.filter((s) => {
    const q = historyQuery.trim().toLowerCase()
    if (!q) return true
    const title = (s.title || '').toLowerCase()
    const sid = (s.session_id || '').toLowerCase()
    return title.includes(q) || sid.includes(q)
  })

  // UI nicety: check if we have any citation links to render
  const anyCitationLink = citationItems.length > 0 && citationItems.some((ci) => !!ci.link)

  useEffect(() => {
    loadHistorySessions()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedHistorySession) {
      loadHistoryDetail(selectedHistorySession)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedHistorySession])

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort()
    }
  }, [])

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
          id="research-query"
          aria-label="Research query"
          aria-busy={loading}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full min-h-[90px] rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          placeholder="Describe what you want the bio research agent to investigate..."
        />
        <div className="flex items-center gap-2 flex-wrap">
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
          {loading && (
            <button
              onClick={() => streamAbortRef.current?.abort()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-destructive/50 text-destructive bg-background hover:bg-destructive/10"
            >
              Cancel Stream
            </button>
          )}
        </div>
        {error && <div className="text-sm text-destructive">{error}</div>}
        <div className="text-xs text-muted-foreground">
          Stage: {streamStage === 'idle' ? 'Idle' : streamStage === 'searching' ? 'Searching sources' : streamStage === 'analyzing' ? 'Analyzing evidence' : streamStage === 'summarizing' ? 'Summarizing' : 'Completed'}
        </div>
      </div>

      <div className="glass-card rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-medium" role="status" aria-live="polite">Research History</div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/settings')}
              className="px-3 py-1 text-xs rounded-lg border border-border hover:bg-muted/40"
            >
              Settings
            </button>
            <button
              onClick={deleteSelectedHistory}
              disabled={!selectedHistorySession || deletingHistory}
              className="px-3 py-1 text-xs rounded-lg border border-destructive/40 text-destructive hover:bg-destructive/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deletingHistory ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>

        <input
          value={historyQuery}
          onChange={(e) => setHistoryQuery(e.target.value)}
          placeholder="Filter sessions by title or id..."
          className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
        />

        {historyError && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs flex items-center justify-between gap-2">
            <span>{historyError}</span>
            <button
              onClick={loadHistorySessions}
              className="px-2 py-1 rounded border border-destructive/40 hover:bg-destructive/20"
            >
              Retry
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label htmlFor="research-history-session" className="text-xs text-muted-foreground">Session</label>
            <select
              id="research-history-session"
              aria-label="Select research history session"
              value={selectedHistorySession}
              onChange={(e) => {
                const sid = e.target.value
                setSelectedHistorySession(sid)
                loadHistoryDetail(sid)
              }}
              className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
            >
              {filteredHistorySessions.map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {((s.title && s.title.trim()) || s.session_id.slice(0, 8))}
                  {s.updated_at ? ` · ${new Date(s.updated_at).toLocaleString()}` : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="text-xs text-muted-foreground rounded-lg bg-muted/20 p-3">
            Research Results: {historyResults.length}
          </div>
        </div>

        {filteredHistorySessions.length === 0 && !historyError && (
          <div className="rounded-lg border border-border bg-muted/20 p-3 text-xs text-muted-foreground flex items-center justify-between gap-2">
            <span>No history sessions found. Run a research query to create your first session.</span>
            <button
              onClick={runResearch}
              disabled={loading || !query.trim()}
              className="px-3 py-1 rounded border border-border hover:bg-muted/40 disabled:opacity-50"
            >
              Run Now
            </button>
          </div>
        )}

        {historyResults.length > 0 && (
          <div className="grid grid-cols-1 gap-3">
            <div className="rounded-lg border border-border p-3 bg-muted/10">
              <div className="text-xs font-medium mb-2">Task Results</div>
              <div className="max-h-[260px] overflow-y-auto space-y-2">
                {historyResults.map((r, idx) => (
                  <div key={`${r.agent_id}-${idx}`} className="rounded-md bg-background p-2 border border-border/60">
                    <div className="text-[10px] text-muted-foreground mb-1">{r.agent_id}</div>
                    <MarkdownBlock content={r.result} className="prose-p:my-1 prose-li:my-0.5" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {(timeline.length > 0 || sources.length > 0 || knowledge.length > 0) && (
        <div className="glass-card rounded-xl p-4 space-y-3 border border-primary/20 shadow-lg shadow-primary/10" role="status" aria-live="polite" aria-busy={loading}>
          <div className="text-sm font-medium bg-gradient-to-r from-primary via-cta to-primary bg-clip-text text-transparent">Live Research Timeline</div>
          {timeline.length > 0 && (
            <div className="space-y-2">
              {timeline.map((item, i) => (
                <div key={`${item}-${i}`} className="rounded-lg border border-border bg-background/70 px-3 py-2 text-xs animate-slide-up">
                  <span className="mr-2">⚡</span>{item}
                </div>
              ))}
            </div>
          )}

          {sources.length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">Sources (Websites / Papers)</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="rounded-lg border border-cyan-400/30 p-3 bg-cyan-500/5">
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
                <div className="rounded-lg border border-violet-400/30 p-3 bg-violet-500/5">
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
              <div className="space-y-2">
                {knowledge.map((k, i) => (
                  <div key={`${k}-${i}`} className="rounded-lg border border-emerald-400/30 bg-emerald-500/5 px-3 py-2 text-xs">
                    🧠 {k}
                  </div>
                ))}
              </div>
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
                <div className="text-muted-foreground">Citations</div>
                <div className="mt-1 font-medium">{citationItems.length}</div>
              </div>
            </div>
            <div className="mt-3">
              <button
                onClick={() => {
                  const seed = result.summary || result.research || query
                  navigate('/chat', { state: { seedMessage: `Please continue from this research context:\n\n${seed}` } })
                }}
                className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/40"
              >
                Create Follow-up Chat
              </button>
            </div>
          </div>

          {jsonSummaryPayload && jsonSummaryPayload.title ? (
            <div className="glass-card rounded-xl p-4 border border-primary/20">
              <div className="flex items-center gap-2 mb-2 text-sm text-muted-foreground">
                <Sparkles className="w-4 h-4" /> Title
              </div>
              <div className="text-base font-semibold leading-snug">{String(jsonSummaryPayload.title)}</div>
            </div>
          ) : null}

          {jsonSummaryPayload && (
            <>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {structuredFindings.length > 0 && (
                  <div className="glass-card rounded-xl p-4">
                    <div className="text-sm font-medium mb-2 text-muted-foreground">Key Findings</div>
                    <ul className="text-sm space-y-2 list-disc pl-5">
                      {structuredFindings.map((item, i) => (
                        <li key={`finding-${i}`}>{item}</li>
                      ))}
                    </ul>
                    {hasCaveat(findingsSection?.caveat) && (
                      <div className="mt-3 text-xs text-muted-foreground border-t border-border/60 pt-2">
                        <span className="font-medium">Caveat:</span> {String(findingsSection.caveat)}
                      </div>
                    )}
                  </div>
                )}

                {structuredQuality.length > 0 && (
                  <div className="glass-card rounded-xl p-4">
                    <div className="text-sm font-medium mb-2 text-muted-foreground">Quality Assessment</div>
                    <ul className="text-sm space-y-2 list-disc pl-5">
                      {structuredQuality.map((item, i) => (
                        <li key={`quality-${i}`}>{item}</li>
                      ))}
                    </ul>
                    {hasCaveat(qualitySection?.caveat) && (
                      <div className="mt-3 text-xs text-muted-foreground border-t border-border/60 pt-2">
                        <span className="font-medium">Caveat:</span> {String(qualitySection.caveat)}
                      </div>
                    )}
                  </div>
                )}

                {structuredLimitations.length > 0 && (
                  <div className="glass-card rounded-xl p-4">
                    <div className="text-sm font-medium mb-2 text-muted-foreground">Limitations</div>
                    <ul className="text-sm space-y-2 list-disc pl-5">
                      {structuredLimitations.map((item, i) => (
                        <li key={`limitation-${i}`}>{item}</li>
                      ))}
                    </ul>
                    {hasCaveat(limitationsSection?.caveat) && (
                      <div className="mt-3 text-xs text-muted-foreground border-t border-border/60 pt-2">
                        <span className="font-medium">Caveat:</span> {String(limitationsSection.caveat)}
                      </div>
                    )}
                  </div>
                )}

                {structuredNextSteps.length > 0 && (
                  <div className="glass-card rounded-xl p-4">
                    <div className="text-sm font-medium mb-2 text-muted-foreground">Next Steps</div>
                    <ul className="text-sm space-y-2 list-disc pl-5">
                      {structuredNextSteps.map((item, i) => (
                        <li key={`next-${i}`}>{item}</li>
                      ))}
                    </ul>
                    {hasCaveat(nextStepsSection?.caveat) && (
                      <div className="mt-3 text-xs text-muted-foreground border-t border-border/60 pt-2">
                        <span className="font-medium">Caveat:</span> {String(nextStepsSection.caveat)}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {jsonSummaryPayload.sections && jsonSummaryPayload.sections.length > 0 && (
                <details className="glass-card rounded-xl p-4">
                  <summary className="cursor-pointer text-sm text-muted-foreground">Structured Report Sections</summary>
                  <div className="mt-3 grid grid-cols-1 xl:grid-cols-2 gap-3">
                    {jsonSummaryPayload.sections.map((section, idx) => (
                      <div key={`${String(section.heading || idx)}-${idx}`} className="rounded-lg border border-border bg-muted/20 p-3">
                        <div className="text-sm font-semibold mb-2">{prettyHeading(String(section.heading || `section_${idx + 1}`))}</div>
                        {toStringList(section.key_points).length > 0 ? (
                          <ul className="text-xs space-y-1 list-disc pl-4">
                            {toStringList(section.key_points).map((item, itemIdx) => (
                              <li key={`${item}-${itemIdx}`}>{item}</li>
                            ))}
                          </ul>
                        ) : (
                          <div className="text-xs text-muted-foreground">No bullet points provided.</div>
                        )}
                        {hasCaveat(section.caveat) ? (
                          <div className="mt-2 text-[11px] text-muted-foreground border-t border-border/60 pt-2">
                            <span className="font-medium">Caveat:</span> {String(section.caveat)}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </>
          )}

          <div className="glass-card rounded-xl p-4 border border-primary/20">
            <div className="flex items-center gap-2 mb-3 text-sm text-muted-foreground">
              <Sparkles className="w-4 h-4" /> Executive Summary
            </div>
            <div className="bg-muted/30 rounded-lg p-3 max-h-[420px] overflow-y-auto">
              {executiveSection ? (
                <div className="space-y-3">
                  {toStringList(executiveSection.key_points).length > 0 ? (
                    <ul className="space-y-2 list-disc pl-5 text-sm">
                      {toStringList(executiveSection.key_points).map((item, idx) => (
                        <li key={`${item}-${idx}`}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                  {hasCaveat(executiveSection.caveat) ? (
                    <div className="text-xs text-muted-foreground border-t border-border/60 pt-2">
                      <span className="font-medium">Caveat:</span> {String(executiveSection.caveat)}
                    </div>
                  ) : null}
                </div>
              ) : (jsonSummaryPayload && jsonSummaryPayload.executive_summary) ? (
                <MarkdownBlock content={String(jsonSummaryPayload.executive_summary)} className="prose-p:my-1 prose-li:my-1" />
              ) : (
                <MarkdownBlock content={result?.summary ?? ''} className="prose-p:my-1 prose-li:my-1" />
              )}
            </div>
          </div>

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

          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2 text-sm text-muted-foreground">
              <Search className="w-4 h-4" /> Evidence & Citations
            </div>
            <div className="space-y-4">
              {evidenceItems.length > 0 && (
                <div>
                  <div className="text-xs text-muted-foreground mb-2">Evidence Highlights</div>
                  <ul className="space-y-2 list-disc pl-5 text-sm">
                    {evidenceItems.map((item, idx) => (
                      <li key={`${item}-${idx}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {citationItems.length === 0 ? (
                <div className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                  This run produced a structured summary, but it did not return explicit source links. You can still review the evidence highlights above and the Raw Findings section below.
                </div>
              ) : (
                <>
                  {!anyCitationLink && (
                    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                      Sources were detected, but this run did not return direct URLs. You can use the citation text below to search the original references.
                    </div>
                  )}
                  <ol className="space-y-2 list-decimal pl-5">
                    {citationItems.map((c, idx) => (
                      <li key={`${c.text}-${idx}`} className="text-xs break-all">
                        <span className="mr-2 rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">{c.type}</span>
                        {c.link ? (
                          <a href={c.link} target="_blank" rel="noreferrer" className="text-primary underline">{c.text}</a>
                        ) : (
                          <span>{c.text}</span>
                        )}
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </div>
          </div>

          <details className="glass-card rounded-xl p-4">
            <summary className="cursor-pointer text-sm text-muted-foreground">Raw Findings (Advanced)</summary>
            <div className="mt-3">
              <div className="bg-muted/30 rounded-lg p-3 max-h-[420px] overflow-y-auto">
                <MarkdownBlock content={result.research} className="prose-p:my-1 prose-li:my-1" />
              </div>
            </div>
          </details>
        </div>
      )}
    </div>
  )
}
