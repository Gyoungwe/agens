import { useState, useRef, useEffect } from 'react'
import { MessageList } from './MessageList'
import { InputBar } from './InputBar'
import type { Message } from '@/types'

interface ChatWindowProps {
  messages: Message[]
  isStreaming: boolean
  onSendMessage: (message: string) => void
  onSelectImage?: (file: File | null) => void
  selectedImage?: { name: string; size: number } | null
}

export function ChatWindow({ messages, isStreaming, onSendMessage, onSelectImage, selectedImage }: ChatWindowProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

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
    <div className="flex-1 flex flex-col bg-gradient-to-b from-background to-secondary/20">
      <MessageList messages={messages} isStreaming={isStreaming} />
      <div ref={messagesEndRef} />
      <InputBar
        value={input}
        onChange={setInput}
        onSend={handleSend}
        onSelectImage={onSelectImage}
        selectedImage={selectedImage}
        disabled={isStreaming}
      />
    </div>
  )
}
