import type { RuntimeOutputContract, RuntimeSessionContract } from './runtime'

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

export interface Session extends RuntimeSessionContract {
  status: 'active' | 'completed'
  message_count: number
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

export interface ChatRuntimeOutput extends Omit<RuntimeOutputContract, 'namespace' | 'output_type'> {
  namespace: 'chat_runtime'
  output_type: 'final' | 'partial'
}
