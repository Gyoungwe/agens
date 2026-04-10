export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
  agent_id?: string
  session_id?: string
  metadata?: {
    thinking?: string
    tool_calls?: ToolCall[]
  }
}

export interface ToolCall {
  id: string
  name: string
  arguments: string
  result?: string
}

export interface Session {
  session_id: string
  title: string
  status: 'active' | 'completed'
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatRequest {
  message: string
  session_id?: string
  agent_id?: string
}

export interface ChatResponse {
  session_id: string
  message: Message
  done: boolean
}
