import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import { User, Bot } from 'lucide-react'
import type { Message } from '@/types'

interface MessageItemProps {
  message: Message
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isUser ? 'bg-primary text-primary-foreground' : 'bg-secondary'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2 ${
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : 'bg-muted rounded-tl-sm'
        }`}
      >
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
            {message.content}
          </ReactMarkdown>
        </div>
        <div
          className={`text-xs mt-1 ${
            isUser ? 'text-primary-foreground/60' : 'text-muted-foreground'
          }`}
        >
          {new Date(message.created_at).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
