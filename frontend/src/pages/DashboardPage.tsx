import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout'
import { MessageCircle, Wrench, Brain, CheckCircle, TrendingUp, Activity, Clock3 } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
} from 'recharts'

const COLORS = ['#7C3AED', '#06B6D4', '#A78BFA', '#22D3EE']

interface TraceRun {
  trace_id: string
  run_id: string
  status: string
  planned_tasks: number
  completed_tasks: number
  elapsed_ms: number
  start_time: number
}

export function DashboardPage() {
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const [sessions, skills, memory, approvals] = await Promise.all([
        fetch('/api/sessions').then((r) => r.json()),
        fetch('/api/skills/').then((r) => r.json()),
        fetch('/api/memory/stats').then((r) => r.json()),
        fetch('/api/evolution/approvals').then((r) => r.json()),
      ])
      return {
        sessions: sessions.sessions?.length || 0,
        skills: skills.skills?.length || 0,
        memory: memory.stats?.total || 0,
        pendingApprovals: approvals.approvals?.filter((a: { status: string }) => a.status === 'pending').length || 0,
      }
    },
  })

  const chartData = [
    { name: 'Mon', sessions: 12 },
    { name: 'Tue', sessions: 19 },
    { name: 'Wed', sessions: 15 },
    { name: 'Thu', sessions: 28 },
    { name: 'Fri', sessions: 24 },
    { name: 'Sat', sessions: 18 },
    { name: 'Sun', sessions: 12 },
  ]

  const pieData = [
    { name: 'Research', value: 35 },
    { name: 'Executor', value: 25 },
    { name: 'Writer', value: 20 },
    { name: 'Orchestrator', value: 20 },
  ]

  const { data: tracesData } = useQuery({
    queryKey: ['dashboard-traces'],
    queryFn: async () => fetch('/api/traces?limit=8').then((r) => r.json()),
    refetchInterval: 10000,
  })

  const traces: TraceRun[] = tracesData?.traces || []

  return (
    <div className="flex flex-col h-full">
      <Header title="Dashboard" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Total Sessions"
              value={stats?.sessions || 0}
              icon={MessageCircle}
              color="primary"
            />
            <StatCard
              title="Active Skills"
              value={stats?.skills || 0}
              icon={Wrench}
              color="cta"
            />
            <StatCard
              title="Knowledge Docs"
              value={stats?.memory || 0}
              icon={Brain}
              color="success"
            />
            <StatCard
              title="Pending Approvals"
              value={stats?.pendingApprovals || 0}
              icon={CheckCircle}
              color={stats?.pendingApprovals > 0 ? 'destructive' : 'success'}
              highlight={stats?.pendingApprovals > 0}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="glass-card rounded-2xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-primary" />
                </div>
                <h3 className="text-lg font-semibold">Session Trend (7 days)</h3>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="name" stroke="#6B7280" fontSize={12} />
                    <YAxis stroke="#6B7280" fontSize={12} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="sessions"
                      stroke="#7C3AED"
                      strokeWidth={3}
                      dot={{ fill: '#7C3AED', strokeWidth: 2 }}
                      activeDot={{ r: 6, fill: '#7C3AED' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="glass-card rounded-2xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-primary" />
                </div>
                <h3 className="text-lg font-semibold">Agent Task Distribution</h3>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {pieData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex justify-center gap-6 mt-4">
                {pieData.map((item, index) => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full shadow-sm"
                      style={{ backgroundColor: COLORS[index] }}
                    />
                    <span className="text-sm text-muted-foreground">{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="glass-card rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Recent Traces</h3>
                  <p className="text-xs text-muted-foreground font-mono">Orchestrator runtime observability</p>
                </div>
              </div>
            </div>

            {traces.length === 0 ? (
              <div className="text-sm text-muted-foreground">No trace data yet. Enable `ENABLE_MLFLOW_TRACE=true` to collect run history.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground border-b border-border/50">
                      <th className="py-2 pr-3">Trace</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Tasks</th>
                      <th className="py-2 pr-3">Elapsed</th>
                      <th className="py-2">Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {traces.map((t) => (
                      <tr key={t.run_id} className="border-b border-border/30 last:border-0">
                        <td className="py-2 pr-3 font-mono text-xs">{(t.trace_id || t.run_id).slice(0, 12)}</td>
                        <td className="py-2 pr-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                              t.status === 'success' || t.status === 'finished'
                                ? 'bg-success/10 text-success'
                                : t.status === 'failed'
                                ? 'bg-destructive/10 text-destructive'
                                : 'bg-muted text-muted-foreground'
                            }`}
                          >
                            {t.status || 'unknown'}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">{t.completed_tasks}/{t.planned_tasks}</td>
                        <td className="py-2 pr-3 text-muted-foreground">{Math.max(0, Math.round((t.elapsed_ms || 0) / 1000))}s</td>
                        <td className="py-2 text-muted-foreground">
                          <span className="inline-flex items-center gap-1">
                            <Clock3 className="w-3 h-3" />
                            {t.start_time ? new Date(t.start_time).toLocaleTimeString() : '-'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  highlight,
}: {
  title: string
  value: number
  icon: React.ComponentType<{ className?: string }>
  color: 'primary' | 'cta' | 'success' | 'destructive'
  highlight?: boolean
}) {
  const colorMap = {
    primary: 'from-primary to-primary/80',
    cta: 'from-cta to-cta/80',
    success: 'from-success to-success/80',
    destructive: 'from-destructive to-destructive/80',
  }

  return (
    <div
      className={`glass-card rounded-2xl p-6 transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 ${
        highlight ? 'ring-2 ring-destructive/50' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-muted-foreground">{title}</span>
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colorMap[color]} flex items-center justify-center shadow-lg`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
      <div className="text-3xl font-bold text-foreground">{value}</div>
    </div>
  )
}
