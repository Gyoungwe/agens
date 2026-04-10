import { useRef, type KeyboardEvent, type ChangeEvent } from 'react'
import { Send, Sparkles } from 'lucide-react'

interface InputBarProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled?: boolean
}

export function InputBar({ value, onChange, onSend, disabled }: InputBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }

  return (
    <div className="border-t border-border/50 p-4 bg-card/50 backdrop-blur-sm">
      <div className="flex gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Message the agents..."
            rows={1}
            className="w-full px-4 py-3 pl-12 rounded-2xl border border-border/50 bg-card resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200 disabled:opacity-50 text-foreground placeholder:text-muted-foreground"
            style={{ maxHeight: '120px' }}
          />
          <Sparkles className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
        </div>
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="px-5 py-3 bg-gradient-to-r from-primary to-primary/80 text-primary-foreground rounded-2xl font-medium hover:shadow-lg hover:shadow-primary/25 hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center gap-2 cursor-pointer"
        >
          <Send className="w-4 h-4" />
          <span className="hidden sm:inline">Send</span>
        </button>
      </div>
      <div className="max-w-4xl mx-auto mt-2">
        <p className="text-xs text-muted-foreground/60 text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
