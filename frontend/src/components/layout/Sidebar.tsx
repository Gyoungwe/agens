import { NavLink } from 'react-router-dom'
import { useApprovalStore } from '@/store'
import {
  MessageCircle,
  BarChart3,
  Wrench,
  BookOpen,
  CheckCircle,
  ScrollText,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: MessageCircle, label: 'Chat' },
  { to: '/dashboard', icon: BarChart3, label: 'Dashboard' },
  { to: '/skills', icon: Wrench, label: 'Skills' },
  { to: '/knowledge', icon: BookOpen, label: 'Knowledge' },
  { to: '/approvals', icon: CheckCircle, label: 'Approvals', badge: true },
  { to: '/sessions', icon: ScrollText, label: 'Sessions' },
]

export function Sidebar() {
  const { pendingCount } = useApprovalStore()

  return (
    <aside className="w-64 bg-card border-r border-border flex flex-col">
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-semibold tracking-tight">🚀 Agens</h1>
        <p className="text-xs text-muted-foreground">Multi-Agent System</p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            <span className="flex-1">{label}</span>
            {badge && pendingCount > 0 && (
              <span className="bg-destructive text-destructive-foreground text-xs font-bold px-1.5 py-0.5 rounded-full">
                {pendingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-border">
        <div className="text-xs text-muted-foreground">
          v1.0.0
        </div>
      </div>
    </aside>
  )
}
