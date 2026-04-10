import { useRef, type KeyboardEvent, type ChangeEvent } from 'react'
import { Send } from 'lucide-react'

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
    <div className="border-t border-border p-4 bg-card">
      <div className="flex gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Type a message..."
            rows={1}
            className="w-full px-4 py-3 rounded-xl border border-input bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
            style={{ maxHeight: '120px' }}
          />
        </div>
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <Send className="w-4 h-4" />
          Send
        </button>
      </div>
    </div>
  )
}
