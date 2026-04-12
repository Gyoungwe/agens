import { MessageItem } from './MessageItem'
import { Sparkles } from 'lucide-react'
import type { Message } from '@/types'

interface MessageListProps {
  messages: Message[]
  isStreaming: boolean
  streamStageLabel?: string
}

export function MessageList({ messages, isStreaming, streamStageLabel }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center animate-float">
            <Sparkles className="w-10 h-10 text-primary" />
          </div>
          <h3 className="text-xl font-semibold text-foreground mb-2">Start a Conversation</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Send a message to begin chatting with the multi-agent system. 
            The agents will collaborate to help you accomplish your tasks.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden p-6 space-y-6">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
      {isStreaming && (
        <div className="flex items-start gap-3 animate-slide-up">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-cta flex items-center justify-center flex-shrink-0 shadow-lg shadow-primary/20">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div className="bg-card rounded-2xl rounded-tl-sm px-4 py-3 shadow-lg border border-border/50">
            <div className="text-[11px] text-muted-foreground mb-1">
              {streamStageLabel || 'Assistant is thinking...'}
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-primary animate-typing" />
              <div className="w-2 h-2 rounded-full bg-primary animate-typing [animation-delay:0.2s]" />
              <div className="w-2 h-2 rounded-full bg-primary animate-typing [animation-delay:0.4s]" />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
