import { NavLink } from 'react-router-dom'
import { useApprovalStore } from '@/store'
import {
  BarChart3,
  Wrench,
  BookOpen,
  CheckCircle,
  ScrollText,
  Bot,
  SlidersHorizontal,
  Sparkles,
  MessageSquare,
  Microscope,
} from 'lucide-react'

const navItems = [
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/research', icon: Microscope, label: 'Research' },
  { to: '/dashboard', icon: BarChart3, label: 'Dashboard' },
  { to: '/providers', icon: Bot, label: 'Models' },
  { to: '/skills', icon: Wrench, label: 'Skills' },
  { to: '/knowledge', icon: BookOpen, label: 'Knowledge' },
  { to: '/approvals', icon: CheckCircle, label: 'Approvals', badge: true },
  { to: '/sessions', icon: ScrollText, label: 'Sessions' },
  { to: '/agent-settings', icon: SlidersHorizontal, label: 'Agent Settings' },
]

export function Sidebar() {
  const { pendingCount } = useApprovalStore()

  return (
    <aside className="w-64 bg-card border-r border-border flex flex-col h-full">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-cta flex items-center justify-center shadow-lg shadow-primary/25">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-foreground">Agens</h1>
            <p className="text-xs text-muted-foreground">Multi-Agent System</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer ${
                isActive
                  ? 'bg-gradient-to-r from-primary to-primary/80 text-primary-foreground shadow-lg shadow-primary/25'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={`w-5 h-5 transition-transform duration-200 ${isActive ? 'scale-110' : 'group-hover:scale-105'}`} />
                <span className="flex-1">{label}</span>
                {badge && pendingCount > 0 && (
                  <span className="bg-cta text-cta-foreground text-xs font-bold px-2 py-0.5 rounded-full shadow-sm">
                    {pendingCount}
                  </span>
                )}
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-cta rounded-r-full" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="glass-card rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs font-medium text-muted-foreground">System Status</span>
          </div>
          <div className="text-xs text-foreground font-mono">All agents online</div>
        </div>
      </div>
    </aside>
  )
}
