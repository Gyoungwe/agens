import { MessageItem } from './MessageItem'
import type { Message } from '@/types'

interface MessageListProps {
  messages: Message[]
  isStreaming: boolean
}

export function MessageList({ messages, isStreaming }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        <div className="text-center">
          <div className="text-4xl mb-4">🤖</div>
          <h3 className="text-lg font-medium mb-2">Start a conversation</h3>
          <p className="text-sm">Send a message to begin chatting with the agents</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
      {isStreaming && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <div className="loading-dots">
            <div className="loading-dot" />
            <div className="loading-dot" />
            <div className="loading-dot" />
          </div>
          <span className="text-sm">Agent is thinking...</span>
        </div>
      )}
    </div>
  )
}
