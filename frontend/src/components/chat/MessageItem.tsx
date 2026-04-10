import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import { User, Sparkles } from 'lucide-react'
import type { Message } from '@/types'

interface MessageItemProps {
  message: Message
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : ''} animate-slide-up`}>
      <div
        className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg transition-transform duration-200 hover:scale-105 ${
          isUser 
            ? 'bg-gradient-to-br from-primary to-primary/80 text-primary-foreground' 
            : 'bg-gradient-to-br from-primary to-cta text-white'
        }`}
      >
        {isUser ? <User className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
      </div>

      <div
        className={`max-w-[75%] rounded-2xl px-5 py-3 transition-all duration-200 ${
          isUser
            ? 'bg-gradient-to-br from-primary to-primary/80 text-primary-foreground rounded-tr-sm shadow-lg shadow-primary/20'
            : 'bg-card border border-border/50 rounded-tl-sm shadow-lg'
        }`}
      >
        <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
          <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
            {message.content}
          </ReactMarkdown>
        </div>
        <div
          className={`text-xs mt-2 font-mono ${
            isUser ? 'text-primary-foreground/60' : 'text-muted-foreground/60'
          }`}
        >
          {new Date(message.created_at).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
