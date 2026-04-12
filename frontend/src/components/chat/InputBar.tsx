import { useRef, type KeyboardEvent, type ChangeEvent } from 'react'
import { Send, Sparkles, ImagePlus, X } from 'lucide-react'

interface InputBarProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  lastUserMessage?: string
  onSelectImage?: (file: File | null) => void
  selectedImage?: { name: string; size: number } | null
  disabled?: boolean
}

const QUICK_PROMPTS = [
  'Summarize current progress',
  'Continue from pending tasks',
  'Research this topic deeply',
]

export function InputBar({ value, onChange, onSend, lastUserMessage, onSelectImage, selectedImage, disabled }: InputBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0] || null
            onSelectImage?.(file)
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          aria-label="Attach image"
          className="px-3 py-3 rounded-2xl border border-border/50 bg-card hover:bg-muted/40 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          title="Attach image"
        >
          <ImagePlus className="w-4 h-4" />
        </button>
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Message the agents..."
            aria-label="Message input"
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

      <div className="max-w-4xl mx-auto mt-2 flex flex-wrap items-center gap-2">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onChange(prompt)}
            disabled={disabled}
            className="px-2.5 py-1 text-[11px] rounded-full border border-border bg-background hover:bg-muted/40 disabled:opacity-50 cursor-pointer"
          >
            {prompt}
          </button>
        ))}
        <button
          onClick={() => onChange('')}
          disabled={disabled || !value}
          className="px-2.5 py-1 text-[11px] rounded-full border border-border bg-background hover:bg-muted/40 disabled:opacity-50 cursor-pointer"
        >
          Clear
        </button>
        <button
          onClick={() => onChange(lastUserMessage || '')}
          disabled={disabled || !lastUserMessage}
          className="px-2.5 py-1 text-[11px] rounded-full border border-border bg-background hover:bg-muted/40 disabled:opacity-50 cursor-pointer"
        >
          Resend Last
        </button>
      </div>

      {selectedImage && (
        <div className="max-w-4xl mx-auto mt-2 flex items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-2 px-2 py-1 rounded border border-border bg-muted/30">
            <ImagePlus className="w-3 h-3" />
            {selectedImage.name} ({Math.round(selectedImage.size / 1024)}KB)
          </span>
          <button
            onClick={() => onSelectImage?.(null)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border hover:bg-muted/40 cursor-pointer"
          >
            <X className="w-3 h-3" /> Remove
          </button>
        </div>
      )}
      <div className="max-w-4xl mx-auto mt-2">
        <p className="text-xs text-muted-foreground/60 text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
