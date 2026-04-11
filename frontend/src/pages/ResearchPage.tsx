import { useState } from 'react'
import { Search, FlaskConical, Sparkles } from 'lucide-react'
import { researchApi } from '@/api/research'

export function ResearchPage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ research: string; summary: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runResearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const { data } = await researchApi.run({ query: query.trim() })
      setResult({ research: data.research, summary: data.summary })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Research failed')
    } finally {
      setLoading(false)
    }
  }

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
        <button
          onClick={runResearch}
          disabled={loading || !query.trim()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <Search className="w-4 h-4" />
          {loading ? 'Researching...' : 'Run Research'}
        </button>
        {error && <div className="text-sm text-destructive">{error}</div>}
      </div>

      {result && (
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
      )}
    </div>
  )
}
