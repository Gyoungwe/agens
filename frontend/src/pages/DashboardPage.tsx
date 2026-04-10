import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout'
import { BarChart } from 'lucide-react'
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

const COLORS = ['#2563eb', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6']

export function DashboardPage() {
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const [sessions, skills, memory, approvals] = await Promise.all([
        fetch('/api/sessions').then((r) => r.json()),
        fetch('/api/skills/').then((r) => r.json()),
        fetch('/api/memory/stats').then((r) => r.json()),
        fetch('/api/approvals').then((r) => r.json()),
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

  return (
    <div className="flex flex-col h-full">
      <Header title="Dashboard" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Total Sessions"
              value={stats?.sessions || 0}
              icon={BarChart}
            />
            <StatCard
              title="Active Skills"
              value={stats?.skills || 0}
              icon={BarChart}
            />
            <StatCard
              title="Knowledge Docs"
              value={stats?.memory || 0}
              icon={BarChart}
            />
            <StatCard
              title="Pending Approvals"
              value={stats?.pendingApprovals || 0}
              icon={BarChart}
              highlight
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4">Session Trend (7 days)</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                    <YAxis stroke="#64748b" fontSize={12} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="sessions"
                      stroke="#2563eb"
                      strokeWidth={2}
                      dot={{ fill: '#2563eb' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4">Agent Task Distribution</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
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
              <div className="flex justify-center gap-4 mt-4">
                {pieData.map((item, index) => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COLORS[index] }}
                    />
                    <span className="text-sm text-muted-foreground">{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
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
  highlight,
}: {
  title: string
  value: number
  icon: React.ComponentType<{ className?: string }>
  highlight?: boolean
}) {
  return (
    <div
      className={`bg-card rounded-xl border border-border p-6 ${
        highlight && value > 0 ? 'border-destructive/50' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-muted-foreground">{title}</span>
        <Icon className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="text-3xl font-bold">{value}</div>
    </div>
  )
}
