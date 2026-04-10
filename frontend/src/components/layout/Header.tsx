import { useQuery } from '@tanstack/react-query'
import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '@/store'

interface HeaderProps {
  title?: string
}

export function Header({ title }: HeaderProps) {
  const { username, logout } = useAuthStore()

  const { data: providers } = useQuery({
    queryKey: ['providers'],
    queryFn: async () => {
      const res = await fetch('/api/providers')
      return res.json()
    },
  })

  return (
    <header className="h-14 bg-card border-b border-border flex items-center justify-between px-4">
      <div className="flex items-center gap-4">
        {title && <h2 className="text-sm font-medium">{title}</h2>}
      </div>

      <div className="flex items-center gap-3">
        <select className="text-sm bg-secondary border border-border rounded-lg px-3 py-1.5">
          <option value="deepseek">{providers?.[0]?.model || 'Select Model'}</option>
        </select>

        <button
          onClick={logout}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <User className="w-4 h-4" />
          <span className="hidden sm:inline">{username || 'User'}</span>
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
