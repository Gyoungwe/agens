import { useEffect, useState } from 'react'
import { Header } from '@/components/layout'
import { channelsApi } from '@/api/channels'

export function ChannelsPage() {
  const [wecomToken, setWecomToken] = useState('')
  const [feishuAppId, setFeishuAppId] = useState('')
  const [status, setStatus] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [runtime, setRuntime] = useState<{
    runtime_ready: boolean
    active_channel_sessions: number
    wecom_enabled: boolean
    feishu_enabled: boolean
    wecom_webhook: string
    feishu_webhook: string
  } | null>(null)

  const load = async () => {
    try {
      setError(null)
      const [cfg, st] = await Promise.all([channelsApi.getConfig(), channelsApi.getStatus()])
      setStatus(
        `WeCom: ${cfg.data.wecom.configured ? cfg.data.wecom.token_masked : 'Not configured'} | Feishu: ${cfg.data.feishu.configured ? cfg.data.feishu.app_id_masked : 'Not configured'}`
      )
      setRuntime(st.data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      throw e
    }
  }

  useEffect(() => {
    load().catch((e) => setStatus(`Load failed: ${e instanceof Error ? e.message : String(e)}`))
  }, [])

  const save = async () => {
    try {
      setError(null)
      await channelsApi.saveConfig({
        wecom: { bot_token: wecomToken || undefined },
        feishu: { bot_app_id: feishuAppId || undefined },
      })
      setWecomToken('')
      setFeishuAppId('')
      await load()
      setStatus((prev) => `${prev}\nSaved successfully.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus(`Save failed: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <Header title="Channels" />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm flex items-center justify-between gap-3">
            <span>Channels error: {error}</span>
            <button onClick={() => load()} className="px-3 py-1.5 text-xs rounded border border-destructive/40 hover:bg-destructive/20">
              Retry
            </button>
          </div>
        )}
        <div className="glass-card rounded-xl p-4 space-y-3">
          <h3 className="text-base font-semibold">Channel Pairing</h3>
          <p className="text-xs text-muted-foreground">
            Configure real pairing credentials for WeCom / Feishu bot webhooks.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">WeCom Bot Token</label>
              <input
                type="password"
                value={wecomToken}
                onChange={(e) => setWecomToken(e.target.value)}
                placeholder="Enter new token"
                className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Feishu Bot App ID</label>
              <input
                type="text"
                value={feishuAppId}
                onChange={(e) => setFeishuAppId(e.target.value)}
                placeholder="Enter app id"
                className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
              />
            </div>
          </div>

          <button
            onClick={save}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm"
          >
            Save Pairing
          </button>
        </div>

        <div className="glass-card rounded-xl p-4">
          <h3 className="text-base font-semibold mb-2">Status</h3>
          <pre className="text-xs whitespace-pre-wrap bg-muted/30 rounded-lg p-3">
            {status || 'Loading...'}
            {runtime
              ? `\nRuntime ready: ${runtime.runtime_ready}\nActive channel sessions: ${runtime.active_channel_sessions}\nWeCom webhook: ${runtime.wecom_webhook}\nFeishu webhook: ${runtime.feishu_webhook}`
              : ''}
          </pre>
        </div>
      </div>
    </div>
  )
}
