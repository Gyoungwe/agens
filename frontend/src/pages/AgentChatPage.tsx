import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout'
import { agentsApi } from '@/api'
import { Bot, Send, User } from 'lucide-react'

interface AgentChatMessage {
  role: 'user' | 'assistant'
  content: string
  at: string
}

export function AgentChatPage() {
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<AgentChatMessage[]>([])

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => (await agentsApi.getAgents()).data,
  })

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      if (!selectedAgent) throw new Error('Please select an agent first')
      const response = await agentsApi.chatWithAgent(selectedAgent, { message })
      return response.data
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.response || '(no response)', at: new Date().toISOString() },
      ])
    },
    onError: (err) => {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${msg}`, at: new Date().toISOString() },
      ])
    },
  })

  const handleSend = async () => {
    const content = input.trim()
    if (!content) return
    setMessages((prev) => [...prev, { role: 'user', content, at: new Date().toISOString() }])
    setInput('')
    await chatMutation.mutateAsync(content)
  }

  return (
    <div className="flex flex-col h-full">
      <Header title="Agent Chat" />
      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4 p-4">
        <div className="glass-card rounded-2xl p-4 overflow-y-auto">
          <h3 className="text-sm font-semibold mb-3">Agents</h3>
          <div className="space-y-2">
            {(agentsData?.agents || []).map((agent: { agent_id: string; name?: string; role?: string }) => (
              <button
                key={agent.agent_id}
                onClick={() => setSelectedAgent(agent.agent_id)}
                className={`w-full text-left p-3 rounded-xl border transition-colors ${
                  selectedAgent === agent.agent_id
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-secondary/50'
                }`}
              >
                <div className="font-medium text-sm">{agent.name || agent.agent_id}</div>
                <div className="text-xs text-muted-foreground">{agent.role || agent.agent_id}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 flex flex-col overflow-hidden">
          <div className="text-sm text-muted-foreground mb-3">
            Current: <span className="font-mono text-foreground">{selectedAgent || 'None selected'}</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {messages.map((m, i) => (
              <div key={`${m.at}-${i}`} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
                {m.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-cta text-white flex items-center justify-center">
                    <Bot className="w-4 h-4" />
                  </div>
                )}
                <div className={`max-w-[80%] px-4 py-2 rounded-xl text-sm ${m.role === 'user' ? 'bg-primary text-white' : 'bg-card border border-border'}`}>
                  {m.content}
                </div>
                {m.role === 'user' && (
                  <div className="w-8 h-8 rounded-lg bg-primary/80 text-white flex items-center justify-center">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-3 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSend()
              }}
              className="flex-1 px-3 py-2 rounded-xl border border-border bg-card text-sm"
              placeholder="Send a debug task to selected agent"
              disabled={!selectedAgent || chatMutation.isPending}
            />
            <button
              onClick={handleSend}
              disabled={!selectedAgent || !input.trim() || chatMutation.isPending}
              className="px-4 py-2 rounded-xl bg-primary text-white disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
