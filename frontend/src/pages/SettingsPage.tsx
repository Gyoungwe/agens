import { Header } from '@/components/layout'
import { useChatPreferencesStore, useChatStore } from '@/store'
import { useNavigate } from 'react-router-dom'
import { CheckCircle, Radio } from 'lucide-react'

export function SettingsPage() {
  const navigate = useNavigate()
  const { defaultChatMode, memoryScope, realtimeLogsEnabled, setDefaultChatMode, setMemoryScope, setRealtimeLogsEnabled } = useChatPreferencesStore()
  const { currentSessionId, addMessage } = useChatStore()

  const runMemorySelfCheck = () => {
    const checklist = [
      '记忆自检步骤：',
      '1) 在同一会话连续发送两条消息（包含可识别事实，如“我的项目代号是 A1”）。',
      '2) 发送“请复述我刚才给出的项目代号”。',
      '3) 切换新会话后再次询问，模型不应继续记住上一会话事实。',
      '4) 如需底层验证：访问 /debug/results/{session_id} 查看 task_results。',
    ].join('\n')

    addMessage({
      id: `system-memory-check-${Date.now()}`,
      role: 'system',
      content: checklist,
      created_at: new Date().toISOString(),
      session_id: currentSessionId || undefined,
    })
    navigate('/chat')
  }

  const summarizeAndContinue = async () => {
    if (!currentSessionId) return
    try {
      const res = await fetch('/api/chat/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: currentSessionId }),
      })
      const data = await res.json()
      const completed = Array.isArray(data.completed) ? data.completed.slice(0, 8) : []
      const pending = Array.isArray(data.pending) ? data.pending.slice(0, 8) : []
      addMessage({
        id: `system-summary-${Date.now()}`,
        role: 'system',
        content: [
          '上下文已总结并继续：',
          `- token usage: ${data.total_tokens ?? 0}/${data.window ?? 0} (${(Number(data.ratio || 0) * 100).toFixed(1)}%)`,
          completed.length ? `- 已完成:\n${completed.map((x: string) => `  • ${x}`).join('\n')}` : '- 已完成: （无提取）',
          pending.length ? `- 待完成:\n${pending.map((x: string) => `  • ${x}`).join('\n')}` : '- 待完成: （无提取）',
        ].join('\n'),
        created_at: new Date().toISOString(),
        session_id: currentSessionId,
      })
      navigate('/chat')
    } catch (e) {
      addMessage({
        id: `system-summary-error-${Date.now()}`,
        role: 'system',
        content: `总结失败：${e instanceof Error ? e.message : String(e)}`,
        created_at: new Date().toISOString(),
        session_id: currentSessionId,
      })
      navigate('/chat')
    }
  }

  return (
    <div className="flex flex-col h-full">
      <Header title="Settings" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-4">
          <div className="glass-card rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-semibold">Chat Preferences</h3>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Default Chat Mode</label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setDefaultChatMode('auto')}
                  className={`px-3 py-1.5 text-xs rounded-lg border ${defaultChatMode === 'auto' ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted/40'}`}
                >
                  Auto
                </button>
                <button
                  onClick={() => setDefaultChatMode('chat')}
                  className={`px-3 py-1.5 text-xs rounded-lg border ${defaultChatMode === 'chat' ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted/40'}`}
                >
                  Normal Chat
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Memory Scope</label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setMemoryScope('session')}
                  className={`px-3 py-1.5 text-xs rounded-lg border ${memoryScope === 'session' ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted/40'}`}
                >
                  Session
                </button>
                <button
                  onClick={() => setMemoryScope('global')}
                  className={`px-3 py-1.5 text-xs rounded-lg border ${memoryScope === 'global' ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted/40'}`}
                >
                  Global
                </button>
              </div>
            </div>

            <div className="pt-2 border-t border-border/60 space-y-2">
              <label className="text-xs text-muted-foreground">Realtime Logs</label>
              <button
                onClick={() => setRealtimeLogsEnabled(!realtimeLogsEnabled)}
                className={`px-3 py-1.5 text-xs rounded-lg border ${realtimeLogsEnabled ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted/40'}`}
              >
                {realtimeLogsEnabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>

            <div className="pt-2 border-t border-border/60 space-y-2">
              <label className="text-xs text-muted-foreground">Advanced Session Tools</label>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={runMemorySelfCheck}
                  className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/40"
                >
                  Memory Self-Check
                </button>
                <button
                  onClick={summarizeAndContinue}
                  disabled={!currentSessionId}
                  className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted/40 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Summarize & Continue
                </button>
              </div>
              {!currentSessionId && (
                <div className="text-[11px] text-muted-foreground">Open a chat session first to enable summarize.</div>
              )}
            </div>
          </div>

          <div className="glass-card rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-semibold">Workspace Navigation</h3>
            <p className="text-xs text-muted-foreground">Low-frequency admin pages live here instead of the main sidebar.</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={() => navigate('/approvals')}
                className="flex items-center gap-3 rounded-xl border border-border p-3 text-left hover:bg-muted/30"
              >
                <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                  <CheckCircle className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-medium">Approvals</div>
                  <div className="text-xs text-muted-foreground">Review pending decisions and history.</div>
                </div>
              </button>

              <button
                onClick={() => navigate('/channels')}
                className="flex items-center gap-3 rounded-xl border border-border p-3 text-left hover:bg-muted/30"
              >
                <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                  <Radio className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-medium">Channels</div>
                  <div className="text-xs text-muted-foreground">Configure external communication pairings.</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
