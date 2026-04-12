import { useState, useRef, useEffect } from 'react'
import { MessageList } from './MessageList'
import { InputBar } from './InputBar'
import type { Message } from '@/types'

interface ChatWindowProps {
  messages: Message[]
  isStreaming: boolean
  streamStageLabel?: string
  onSendMessage: (message: string) => void
  onSelectImage?: (file: File | null) => void
  selectedImage?: { name: string; size: number } | null
}

export function ChatWindow({ messages, isStreaming, streamStageLabel, onSendMessage, onSelectImage, selectedImage }: ChatWindowProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user')?.content || ''

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = () => {
    if (input.trim()) {
      onSendMessage(input)
      setInput('')
    }
  }

  return (
    <div className="h-full min-w-0 overflow-hidden flex flex-col bg-gradient-to-b from-background to-secondary/20">
      <MessageList messages={messages} isStreaming={isStreaming} streamStageLabel={streamStageLabel} />
      <div ref={messagesEndRef} />
      <InputBar
        value={input}
        onChange={setInput}
        onSend={handleSend}
        lastUserMessage={lastUserMessage}
        onSelectImage={onSelectImage}
        selectedImage={selectedImage}
        disabled={isStreaming}
      />
    </div>
  )
}
