import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout'
import { useBioEvents } from '@/hooks/useBioEvents'
import { providersApi } from '@/api/providers'
import { Dna, Play, AlertTriangle, CheckCircle2, Clock, ChevronDown, ChevronRight, X, FileText, HardDrive, Settings2, ShieldAlert } from 'lucide-react'
import { bioApi } from '@/api/bio'

function formatElapsed(ms?: number): string {
  const safeMs = ms || 0
  if (safeMs < 1000) return `${safeMs}ms`
  return `${(safeMs / 1000).toFixed(1)}s`
}

function describeWaiting(stage: import('@/types/event').BioStageStatus): string {
  if (stage.status === 'timeout') return 'Stage timed out'
  if (stage.status === 'error') return 'Stage failed'
  if (stage.status === 'ok') return 'Completed'
  switch (stage.waiting_for) {
    case 'agent_start':
      return 'Dispatching task to agent'
    case 'llm_start':
      return 'Agent received task'
    case 'thinking':
      return 'Model is reasoning'
    case 'tool_or_llm_call':
      return 'Waiting for model/tool response'
    case 'post_processing':
      return 'First response received'
    case 'model_response':
      return 'Awaiting model response'
    default:
      return stage.status === 'running' ? 'Running' : 'Queued'
  }
}

function LiveStageCard({ name, stage }: { name: string; stage: import('@/types/event').BioStageStatus }) {
  const [expanded, setExpanded] = useState(false)

  const isRunning = stage.status === 'running'
  const isOk = stage.status === 'ok'
  const isError = stage.status === 'error'
  const isTimeout = stage.status === 'timeout'

  const statusChip = isOk
    ? 'bg-success/10 text-success'
    : isTimeout
      ? 'bg-amber-500/10 text-amber-600'
      : isError
        ? 'bg-destructive/10 text-destructive'
        : 'bg-muted text-muted-foreground'

  const statusIcon = isOk
    ? <CheckCircle2 className="w-4 h-4" />
    : isTimeout
      ? <Clock className="w-4 h-4" />
      : isError
        ? <AlertTriangle className="w-4 h-4" />
        : isRunning
          ? <span className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          : <Clock className="w-4 h-4" />

  const pulseClass = isRunning ? 'shadow-primary/20 shadow-lg' : ''

  return (
    <div className={`glass-card rounded-xl p-4 transition-all duration-500 ${pulseClass}`}>
      <div className="flex items-center gap-3">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-muted-foreground hover:text-foreground cursor-pointer"
          aria-label="toggle stage"
        >
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold capitalize">{name}</span>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusChip}`}>
              {statusIcon}
              {stage.status}
            </span>
          </div>
          <div className="text-xs text-muted-foreground font-mono mt-1">
            {stage.agent_id && `agent=${stage.agent_id}`}
            {(stage.wait_ms || stage.elapsed_ms) > 0 && ` · elapsed=${formatElapsed(stage.wait_ms || stage.elapsed_ms)}`}
            {stage.first_response_received && ' · first response received'}
          </div>
          <div className="mt-2">
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${isOk ? 'bg-success' : isTimeout ? 'bg-amber-500' : isError ? 'bg-destructive' : 'bg-primary'}`}
                style={{ width: `${stage.progress_pct ?? (isOk ? 100 : isRunning ? 25 : 0)}%` }}
              />
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {describeWaiting(stage)}
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 border-t border-border pt-3 space-y-2">
          {stage.error && (
            <div className="text-sm text-destructive bg-destructive/5 rounded-lg px-3 py-2">
              Error: {stage.error}
            </div>
          )}
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Output</div>
            <pre className="text-xs whitespace-pre-wrap bg-muted/30 rounded-lg p-3 max-h-56 overflow-y-auto">
              {stage.output || '(waiting or empty)'}
            </pre>
          </div>
          {stage.provenance && (
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Provenance</div>
              <div className="space-y-1.5 text-xs">
                <div className="flex gap-2">
                  <span className="text-muted-foreground shrink-0">Provider:</span>
                  <span className="font-mono bg-muted/30 px-1.5 py-0.5 rounded">{stage.provenance.provider_id || 'default'}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-muted-foreground shrink-0">Inputs:</span>
                  <span className="font-mono bg-muted/30 px-1.5 py-0.5 rounded">
                    {Object.entries(stage.provenance.inputs || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(' · ')}
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-muted-foreground shrink-0">Params:</span>
                  <span className="font-mono bg-muted/30 px-1.5 py-0.5 rounded">
                    {Object.entries(stage.provenance.params || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(' · ')}
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-muted-foreground shrink-0">Stage elapsed:</span>
                  <span className="font-mono">{formatElapsed(stage.provenance.elapsed_ms)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const ALL_STAGES = ['planning', 'codegen', 'qc', 'report', 'evolution']

function normalizeAssayType(value: string): string {
  const normalized = value.trim().toLowerCase().replace(/[-\s]+/g, '_')
  if (!normalized) return 'other'
  return normalized
}

function parseSampleSheet(raw: string): import('@/api/bio').WorkflowIntentSpec['sample_sheet'] {
  if (!raw.trim()) return undefined
  const lines = raw.trim().split('\n')
  const sampleCount = lines.filter((l) => l.trim() && !l.startsWith('#')).length
  const groups: string[] = []
  const hasControl = lines.some((l) => /\bcontrol\b/i.test(l))
  lines.forEach((line) => {
    const match = line.match(/condition[=:]([^\s,]+)/i) || line.match(/group[=:]([^\s,]+)/i)
    if (match && !groups.includes(match[1])) groups.push(match[1])
  })
  return { sample_count: sampleCount, groups, has_control: hasControl, design_summary: raw.trim().slice(0, 200) }
}

function parseReferenceBundle(raw: string): import('@/api/bio').WorkflowIntentSpec['reference_bundle'] {
  if (!raw.trim()) return undefined
  const lines = raw.trim().split('\n')
  const result: { genome?: string; annotation?: string; dbs: string[] } = { dbs: [] }
  lines.forEach((line) => {
    const [key, ...valParts] = line.split('=')
    const val = valParts.join('=').trim()
    if (!key || !val) return
    if (key === 'genome') result.genome = val
    else if (key === 'annotation') result.annotation = val
    else if (key === 'index' || key === 'dbs') result.dbs.push(val)
  })
  return result
}

function parseConstraints(raw: string): import('@/api/bio').WorkflowIntentSpec['constraints'] {
  if (!raw.trim()) return undefined
  const lines = raw.trim().split('\n')
  const result: { time_budget?: string; compute_budget?: string; privacy_level?: 'low' | 'medium' | 'high'; internet_allowed?: boolean } = {}
  lines.forEach((line) => {
    const [key, ...valParts] = line.split('=')
    const val = valParts.join('=').trim()
    if (!key || !val) return
    if (key === 'max_ram' || key === 'max_cores' || key === 'time_limit') {
      if (!result.compute_budget) result.compute_budget = ''
      result.compute_budget += `${key}=${val} `
    } else if (key === 'storage' || key === 'output_dir') {
      // ignore
    } else if (key === 'time_budget') {
      result.time_budget = val
    }
  })
  return Object.keys(result).length > 0 ? result : undefined
}

function tryParseJson(text?: string): Record<string, unknown> | null {
  if (!text) return null
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null
  } catch {
    return null
  }
}

export function BioWorkflowPage() {
  const [goal, setGoal] = useState('给出一个最小可执行生信流程模板')
  const [dataset, setDataset] = useState('demo-min')
  const [scopeId, setScopeId] = useState('')
  const [providerId, setProviderId] = useState('')
  const [continueOnError, setContinueOnError] = useState(true)
  const [assayType, setAssayType] = useState('')
  const [expectedOutputs, setExpectedOutputs] = useState('')
  const [sampleSheet, setSampleSheet] = useState('')
  const [referenceBundle, setReferenceBundle] = useState('')
  const [constraints, setConstraints] = useState('')
  const [userAnswer, setUserAnswer] = useState('')
  const [resumeLoading, setResumeLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [intentInfo, setIntentInfo] = useState<import('@/api/bio').ConfirmIntentResponse | null>(null)
  const [finalResult, setFinalResult] = useState<import('@/api/bio').BioWorkflowResponse | null>(null)
  const { stream, startStream, cancelStream, clearStream } = useBioEvents()
  const { data: providers = [] } = useQuery({
    queryKey: ['providers-list-bio-workflow'],
    queryFn: async () => (await providersApi.getProviders()).data,
  })
  const activeProviderId = useMemo(
    () => providerId || providers.find((provider) => provider.active)?.id || '',
    [providerId, providers],
  )
  const { data: providerHealth } = useQuery({
    queryKey: ['provider-health-bio-workflow', activeProviderId],
    queryFn: async () => (await providersApi.getHealth(activeProviderId || undefined)).data,
    enabled: !!activeProviderId,
    refetchInterval: 15000,
  })

  useEffect(() => {
    if (!providerId) {
      const activeProvider = providers.find((provider) => provider.active)
      if (activeProvider) {
        setProviderId(activeProvider.id)
      }
    }
  }, [providerId, providers])

  useEffect(() => {
    if (!scopeId.trim()) {
      setScopeId(`bio::${dataset || 'unspecified'}`)
    }
  }, [dataset])

  const isRunning = stream?.isRunning ?? false

  // Plan/generate related state
  const [planInfo, setPlanInfo] = useState<import('@/api/bio').PlanGenerateResponse | null>(null)
  const [planGenerating, setPlanGenerating] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)

  const expectedOutputsList = useMemo(
    () => expectedOutputs.split(',').map((s) => s.trim()).filter(Boolean),
    [expectedOutputs],
  )

  const finalArtifacts = useMemo(() => {
    if (!finalResult?.stage_results) return [] as Array<{ stage: string; artifact: Record<string, unknown> }>
    return finalResult.stage_results
      .map((s) => ({ stage: s.stage, artifact: tryParseJson(s.output || '') }))
      .filter((x): x is { stage: string; artifact: Record<string, unknown> } => x.artifact !== null)
  }, [finalResult])

  const confirmIntent = async () => {
    if (!goal.trim()) return
    setIntentInfo(null)
    setPlanInfo(null)
    setPlanError(null)
    setError(null)
    try {
      const { data } = await bioApi.confirmIntent({
        goal: goal.trim(),
        dataset: dataset.trim() || undefined,
        intent: {
          goal: goal.trim(),
          assay_type: normalizeAssayType(assayType),
          dataset: dataset.trim() || undefined,
          expected_outputs: expectedOutputsList,
          sample_sheet: parseSampleSheet(sampleSheet),
          reference_bundle: parseReferenceBundle(referenceBundle),
          constraints: parseConstraints(constraints),
          fields_requiring_confirmation: [],
          user_confirmed: false,
        },
      })
      setIntentInfo(data)
    } catch (e: unknown) {
      if (e instanceof Error) {
        setPlanError(e.message)
      }
    }
  }

  const generatePlan = async () => {
    setPlanError(null)
    setPlanGenerating(true)
    try {
      const confirmedIntent = intentInfo?.intent ?? {
        goal: goal.trim(),
        assay_type: normalizeAssayType(assayType),
        dataset: dataset.trim() || undefined,
        expected_outputs: expectedOutputsList,
        sample_sheet: parseSampleSheet(sampleSheet),
        reference_bundle: parseReferenceBundle(referenceBundle),
        constraints: parseConstraints(constraints),
        fields_requiring_confirmation: [],
        user_confirmed: true,
      }
      const { data } = await bioApi.generatePlan({
        goal: goal.trim(),
        dataset: dataset.trim() || undefined,
        intent: {
          ...confirmedIntent,
          goal: goal.trim(),
          dataset: dataset.trim() || undefined,
          expected_outputs: expectedOutputsList,
          sample_sheet: parseSampleSheet(sampleSheet) ?? confirmedIntent.sample_sheet,
          reference_bundle: parseReferenceBundle(referenceBundle) ?? confirmedIntent.reference_bundle,
          constraints: parseConstraints(constraints) ?? confirmedIntent.constraints,
          user_confirmed: true,
        },
      })
      setPlanInfo(data)
      setPlanGenerating(false)
    } catch (e: unknown) {
      setPlanError(e instanceof Error ? e.message : 'Failed to generate plan')
      setPlanGenerating(false)
    }
  }

  const runFromPlan = async () => {
    if (!planInfo) return
    try {
      const payloadPlan = planInfo?.plan
      const result = await startStream(
        goal.trim(),
        dataset.trim() || undefined,
        scopeId.trim() || undefined,
        activeProviderId || undefined,
        continueOnError,
        payloadPlan,
      )
      setFinalResult(result)
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== 'AbortError') {
        setError(e.message)
      }
    }
  }

  const runWorkflow = async () => {
    if (!goal.trim()) return
    setError(null)
    setFinalResult(null)
    try {
      const result = await startStream(
        goal.trim(),
        dataset.trim() || undefined,
        scopeId.trim() || undefined,
        activeProviderId || undefined,
        continueOnError,
        planInfo?.plan,
      )
      setFinalResult(result)
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== 'AbortError') {
        setError(e.message)
      }
    }
  }

  const resumeWorkflow = async () => {
    if (!finalResult?.needs_user_input) return
    setResumeLoading(true)
    setError(null)
    try {
      const result = await startStream(
        goal.trim(),
        dataset.trim() || undefined,
        scopeId.trim() || undefined,
        activeProviderId || undefined,
        continueOnError,
        planInfo?.plan,
        {
          user_answer: userAnswer.trim(),
          provided_fields: finalResult.required_fields || [],
        },
      )
      setFinalResult(result)
      setUserAnswer('')
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== 'AbortError') {
        setError(e.message)
      }
    } finally {
      setResumeLoading(false)
    }
  }

  const cancelWorkflow = () => {
    cancelStream()
    clearStream()
    setFinalResult(null)
  }

  return (
    <div className="flex flex-col h-full">
      <Header title="Bio Workflow" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="glass-card rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <Dna className="w-6 h-6 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Bioinformatics MVP Workflow</h2>
                <p className="text-sm text-muted-foreground">Stage-by-stage execution with real-time observability</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Goal</label>
                <textarea
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="w-full min-h-[100px] rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                  placeholder="Describe the bioinformatics objective"
                />
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Dataset</label>
                  <input
                    value={dataset}
                    onChange={(e) => setDataset(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                    placeholder="demo-min"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Assay Type</label>
                  <input
                    value={assayType}
                    onChange={(e) => setAssayType(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                    placeholder="rna_seq / wgs / scrna_seq / metagenomics"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Expected Outputs</label>
                  <input
                    value={expectedOutputs}
                    onChange={(e) => setExpectedOutputs(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                    placeholder="qc_report, report, retrospective"
                  />
                </div>

                <details className="group rounded-xl border border-border bg-muted/10">
                  <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer list-none text-sm font-medium hover:bg-muted/20 rounded-xl">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    Sample Sheet
                    <span className="text-xs text-muted-foreground ml-auto group-open:hidden">optional</span>
                    {sampleSheet && <span className="w-2 h-2 rounded-full bg-primary ml-1" />}
                  </summary>
                  <div className="px-3 pb-3">
                    <textarea
                      value={sampleSheet}
                      onChange={(e) => setSampleSheet(e.target.value)}
                      className="w-full min-h-[80px] rounded-xl border border-border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/40 mt-2"
                      placeholder="sample_id,condition,replicate&#10;SRR001,control,1&#10;SRR002,treatment,1"
                    />
                  </div>
                </details>

                <details className="group rounded-xl border border-border bg-muted/10">
                  <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer list-none text-sm font-medium hover:bg-muted/20 rounded-xl">
                    <HardDrive className="w-4 h-4 text-muted-foreground" />
                    Reference Bundle
                    <span className="text-xs text-muted-foreground ml-auto group-open:hidden">optional</span>
                    {referenceBundle && <span className="w-2 h-2 rounded-full bg-primary ml-1" />}
                  </summary>
                  <div className="px-3 pb-3">
                    <textarea
                      value={referenceBundle}
                      onChange={(e) => setReferenceBundle(e.target.value)}
                      className="w-full min-h-[80px] rounded-xl border border-border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/40 mt-2"
                      placeholder="genome=/data/references/GRCh38.fa&#10;annotation=/data/references/genes.gtf&#10;index=/data/references/star_index/"
                    />
                  </div>
                </details>

                <details className="group rounded-xl border border-border bg-muted/10">
                  <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer list-none text-sm font-medium hover:bg-muted/20 rounded-xl">
                    <Settings2 className="w-4 h-4 text-muted-foreground" />
                    Computational Constraints
                    <span className="text-xs text-muted-foreground ml-auto group-open:hidden">optional</span>
                    {constraints && <span className="w-2 h-2 rounded-full bg-primary ml-1" />}
                  </summary>
                  <div className="px-3 pb-3">
                    <textarea
                      value={constraints}
                      onChange={(e) => setConstraints(e.target.value)}
                      className="w-full min-h-[80px] rounded-xl border border-border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/40 mt-2"
                      placeholder="max_ram=64G&#10;max_cores=16&#10;time_limit=72h&#10;storage=/data/output/"
                    />
                  </div>
                </details>

                <div>
                  <label className="block text-sm font-medium mb-2">Memory Scope</label>
                  <input
                    value={scopeId}
                    onChange={(e) => setScopeId(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                    placeholder="bio::demo-min"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Model Provider</label>
                  <select
                    value={providerId}
                    onChange={(e) => setProviderId(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                    disabled={providers.length === 0}
                  >
                    {providers.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.name} · {provider.model}
                      </option>
                    ))}
                  </select>
                  {providerHealth && (
                    <div className={`mt-2 text-xs font-mono ${providerHealth.healthy ? 'text-success' : 'text-destructive'}`}>
                      health={providerHealth.healthy ? 'healthy' : 'unhealthy'}
                    </div>
                  )}
                </div>

                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={continueOnError}
                    onChange={(e) => setContinueOnError(e.target.checked)}
                    className="w-4 h-4"
                  />
                  Continue on error
                </label>

                <div className="glass-card rounded-xl p-4 mt-2 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold">Task Confirmation</span>
                    {intentInfo && (
                      <span className="text-xs text-muted-foreground">
                        family={intentInfo.workflow_family}
                      </span>
                    )}
                  </div>
                  {intentInfo ? (
                    <div className="space-y-2 text-sm">
                      <div className="text-muted-foreground">
                        Requires confirmation: {intentInfo.requires_confirmation ? 'yes' : 'no'}
                      </div>
                      <div className="text-muted-foreground">
                        Missing/important fields: {intentInfo.intent.fields_requiring_confirmation.join(', ') || 'none'}
                      </div>
                      {intentInfo.intent.system_inference?.inferred_risks?.length ? (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {intentInfo.intent.system_inference.inferred_risks.map((risk, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 border border-amber-500/20">
                              <ShieldAlert className="w-3 h-3" />
                              {risk}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      Confirm the task first so the system can infer workflow family and required fields.
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={confirmIntent}
                      disabled={!goal.trim() || isRunning}
                      className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-semibold rounded-xl border border-border hover:bg-muted/50 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                    >
                      Confirm Intent
                    </button>
                    <button
                      onClick={generatePlan}
                      disabled={!goal.trim() || planGenerating || isRunning}
                      className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-semibold rounded-xl border border-border hover:bg-muted/50 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                    >
                      {planGenerating ? 'Generating...' : 'Generate Plan'}
                    </button>
                  </div>
                </div>

                <div className="glass-card rounded-xl p-4 mt-3 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold">Plan Preview</span>
                    {planInfo?.plan?.workflow_family && (
                      <span className="text-xs text-muted-foreground">family: {planInfo.plan.workflow_family}</span>
                    )}
                  </div>
                  {planInfo ? (
                    <>
                      <div className="text-sm text-muted-foreground">
                        {planInfo.plan.stages.length} stage(s) — dependency graph
                      </div>
                      <div className="relative">
                        {/* Simple DAG visualization */}
                        <div className="flex items-start gap-3 overflow-x-auto pb-2">
                          {planInfo.plan.stages.map((stage, idx) => {
                            const deps = stage.depends_on || []
                            const hasDep = deps.length > 0
                            const isFirst = idx === 0
                            return (
                              <div key={stage.id} className="flex flex-col items-center shrink-0">
                                {idx > 0 && (
                                  <div className="flex items-center w-full mb-1">
                                    <div className="h-px flex-1 bg-border" />
                                    <div className="w-2 h-2 rounded-full border-2 border-border bg-background" />
                                  </div>
                                )}
                                <div className={`w-28 rounded-xl border px-3 py-2 text-center text-sm font-medium ${isFirst ? 'border-primary/40 bg-primary/5' : 'border-border bg-muted/20'}`}>
                                  <div className="capitalize">{stage.name}</div>
                                  <div className="text-xs text-muted-foreground font-mono mt-0.5">
                                    {stage.agent_id?.replace('bio_', '').replace('_agent', '') || '?'}
                                  </div>
                                </div>
                                {hasDep && (
                                  <div className="mt-1 flex flex-wrap justify-center gap-1 max-w-28">
                                    {deps.map((d) => (
                                      <span key={d} className="text-[10px] font-mono text-muted-foreground bg-muted/40 px-1 rounded">
                                        {d}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                      <div className="space-y-2">
                        {planInfo.plan.stages.map((stage) => (
                          <div key={stage.id} className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm">
                            <div className="font-medium capitalize">{stage.name}</div>
                            <div className="text-xs text-muted-foreground">
                              agent={stage.agent_id || 'n/a'} · depends_on={stage.depends_on.join(', ') || 'none'}
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="text-sm text-muted-foreground">No plan generated yet.</div>
                  )}
                  {planInfo && (
                    <div className="flex gap-2">
                      <button
                        onClick={runFromPlan}
                        disabled={isRunning}
                        className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white hover:shadow-lg disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                      >
                        <Play className="w-4 h-4" /> Run Planned Workflow
                      </button>
                    </div>
                  )}
                </div>

                {planError && (
                  <div className="rounded-xl border border-destructive/30 bg-destructive/5 text-destructive px-3 py-2 text-sm">
                    {planError}
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={runWorkflow}
                    disabled={isRunning || !goal.trim()}
                    className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-primary to-primary/80 text-primary-foreground hover:shadow-lg hover:shadow-primary/25 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                  >
                    <Play className="w-4 h-4" />
                    {isRunning ? 'Running...' : 'Run Bio Workflow'}
                  </button>

                  {isRunning && (
                    <button
                      onClick={cancelWorkflow}
                      className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl border border-destructive/30 text-destructive hover:bg-destructive/5 disabled:opacity-60 cursor-pointer"
                      >
                        <X className="w-4 h-4" />
                        Cancel
                      </button>
                    )}
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 text-destructive px-4 py-3 text-sm">
              {error}
            </div>
          )}

          {stream && (
            <div className="space-y-3">
              <div className="glass-card rounded-xl p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm text-muted-foreground">Live Status</div>
                    <div className="text-lg font-semibold">
                      {stream.isRunning ? 'Running' : 'Done'}
                      {stream.failed_stages > 0 && ` · ${stream.failed_stages} failed`}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono mt-1">
                      session={stream.session_id.slice(0, 8)} · trace={stream.trace_id.slice(0, 8)}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono mt-1">
                      provider={stream.provider_id || 'default'} · scope={stream.scope_id || 'default'}
                    </div>
                    {stream.isRunning && (
                      <div className="text-xs text-primary font-medium mt-1">
                        Stream connected. Waiting states below reflect real agent/runtime progress.
                      </div>
                    )}
                  </div>
                  {stream.goal && (
                    <div className="text-xs text-muted-foreground max-w-xs truncate">
                      {stream.goal}
                    </div>
                  )}
                </div>
              </div>

              {ALL_STAGES.map((stageName) => {
                const stage = stream.stages[stageName]
                if (!stage) {
                  return (
                    <div key={stageName} className="glass-card rounded-xl p-4 opacity-40">
                      <div className="flex items-center gap-3">
                        <Clock className="w-4 h-4 text-muted-foreground" />
                        <div>
                          <span className="font-semibold capitalize">{stageName}</span>
                          <span className="ml-2 text-xs text-muted-foreground">waiting</span>
                        </div>
                      </div>
                    </div>
                  )
                }
                return <LiveStageCard key={stageName} name={stageName} stage={stage} />
              })}

              <div className="glass-card rounded-xl p-4">
                <div className="text-sm font-semibold mb-3">Live Agent Logs</div>
                {stream.logs.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No detailed agent logs yet.</div>
                ) : (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {stream.logs.map((log) => (
                      <div key={log.id} className="rounded-lg border border-border bg-muted/20 px-3 py-2">
                        <div className="flex items-center justify-between gap-4 text-xs font-mono text-muted-foreground">
                          <span>{log.event_type}</span>
                          <span>{log.agent_id || 'system'}</span>
                        </div>
                        <div className="mt-1 text-xs whitespace-pre-wrap break-words">
                          {log.message}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {finalResult && !stream?.isRunning && (
            <div className="space-y-4">
              {finalResult.needs_user_input && (
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
                  <div className="flex items-center gap-2 text-amber-700 font-semibold">
                    <AlertTriangle className="w-4 h-4" /> User input required
                  </div>
                  <div className="text-sm text-amber-800 mt-2">
                    {finalResult.user_question || 'Workflow paused and needs your confirmation/input to continue.'}
                  </div>
                  {finalResult.required_fields && finalResult.required_fields.length > 0 && (
                    <div className="mt-2 text-xs text-amber-700 font-mono">
                      required_fields: {finalResult.required_fields.join(', ')}
                    </div>
                  )}
                  <textarea
                    value={userAnswer}
                    onChange={(e) => setUserAnswer(e.target.value)}
                    placeholder="Provide the missing info, e.g. genome=/path/ref.fa annotation=/path/genes.gtf"
                    className="w-full mt-3 min-h-[80px] rounded-lg border border-amber-400/40 bg-white/60 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-amber-500/30"
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={resumeWorkflow}
                      disabled={resumeLoading}
                      className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-semibold rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {resumeLoading ? 'Resuming...' : 'Resume Workflow'}
                    </button>
                  </div>
                </div>
              )}

              <div className="glass-card rounded-xl p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm text-muted-foreground">Final Result</div>
                    <div className="text-lg font-semibold">
                      {finalResult.status} · {finalResult.failed_stages}/{finalResult.total_stages} failed
                    </div>
                    <div className="text-xs text-muted-foreground font-mono mt-1">
                      trace={finalResult.trace_id} · session={finalResult.session_id}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono mt-1">
                      provider={finalResult.provider_id || 'default'} · scope={finalResult.scope_id || 'default'}
                    </div>
                    {finalResult.provider_fallback && (
                      <div className="text-xs text-amber-600 font-medium mt-1">
                        Requested provider was unhealthy, workflow fell back to another healthy provider.
                      </div>
                    )}
                  </div>
                </div>
                <pre className="mt-3 text-xs whitespace-pre-wrap bg-muted/30 rounded-lg p-3 max-h-56 overflow-y-auto">
                  {finalResult.response}
                </pre>
              </div>

              {finalArtifacts.length > 0 && (
                <div className="glass-card rounded-xl p-4">
                  <div className="text-sm text-muted-foreground">Structured stage artifacts</div>
                  <div className="space-y-3 mt-3">
                    {finalArtifacts.map(({ stage, artifact }) => (
                      <div key={stage} className="rounded-lg border border-border bg-muted/20 p-3">
                        <div className="font-semibold capitalize text-sm mb-2">{stage}</div>
                        <pre className="text-xs whitespace-pre-wrap bg-muted/40 rounded p-2 max-h-52 overflow-y-auto">
                          {JSON.stringify(artifact, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {finalResult.stage_results.map((stage) => (
                <LiveStageCard
                  key={stage.trace_id}
                  name={stage.stage}
                  stage={{
                    stage: stage.stage,
                    agent_id: stage.agent_id,
                    trace_id: stage.trace_id,
                    status: stage.status,
                    elapsed_ms: stage.elapsed_ms,
                    output: stage.output,
                    error: stage.error,
                    provenance: stage.provenance,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
