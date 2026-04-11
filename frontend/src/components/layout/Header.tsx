import { useQuery } from '@tanstack/react-query'
import { LogOut, User, ChevronDown } from 'lucide-react'
import { useAuthStore, useLanguageStore } from '@/store'
import { useEffect, useState } from 'react'
import { client } from '@/api'
import { t } from '@/i18n'

interface HeaderProps {
  title?: string
}

export function Header({ title }: HeaderProps) {
  const { username, logout } = useAuthStore()
  const { language, setLanguage } = useLanguageStore()
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [switching, setSwitching] = useState(false)

  const { data: providersData } = useQuery({
    queryKey: ['providers'],
    queryFn: async () => {
      const res = await fetch('/api/providers')
      return res.json()
    },
  })

  const providers = Array.isArray(providersData) ? providersData : (providersData?.providers || [])

  useEffect(() => {
    const active = providers.find((p: { active?: boolean }) => p.active)
    if (active?.id && !selectedProvider) {
      setSelectedProvider(active.id)
    }
  }, [providers, selectedProvider])

  const handleProviderChange = async (providerId: string) => {
    setSelectedProvider(providerId)
    if (!providerId) return

    setSwitching(true)
    try {
      await client.post(`/providers/${providerId}/use`)
    } catch (error) {
      console.error('[provider-switch] failed', error)
      alert('Model switch failed. Check logs/features/providers_*.log')
    } finally {
      setSwitching(false)
    }
  }

  return (
    <header className="h-16 bg-card/80 backdrop-blur-md border-b border-border flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        {title && (
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
            <div className="h-6 w-px bg-border" />
            <span className="text-xs text-muted-foreground font-mono">v1.0.0</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <div className="inline-flex rounded-lg border border-border overflow-hidden" title="Language">
          <button
            onClick={() => setLanguage('en')}
            className={`px-2 py-1 text-xs sm:text-sm ${language === 'en' ? 'bg-primary text-primary-foreground' : 'bg-secondary/50 text-foreground'}`}
          >
            EN
          </button>
          <button
            onClick={() => setLanguage('zh-CN')}
            className={`px-2 py-1 text-xs sm:text-sm ${language === 'zh-CN' ? 'bg-primary text-primary-foreground' : 'bg-secondary/50 text-foreground'}`}
          >
            中文
          </button>
        </div>

        <div className="relative">
          <select
            value={selectedProvider}
            onChange={(e) => handleProviderChange(e.target.value)}
            disabled={switching}
            className="appearance-none w-[150px] sm:w-[210px] bg-secondary/50 border border-border rounded-lg px-3 py-1.5 pr-8 text-xs sm:text-sm font-medium text-foreground cursor-pointer hover:bg-secondary transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-60"
          >
            <option value="">{t('selectModel')}</option>
            {providers?.map((p: { id: string; name: string; model: string }) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
        </div>

        <div className="flex items-center gap-3 pl-4 border-l border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-cta flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-medium hidden sm:inline">{username || t('user')}</span>
          </div>
          <button
            onClick={logout}
            className="p-2 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
            title={t('logout')}
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
