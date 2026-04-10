import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import type { NodeProps } from 'reactflow'

interface AgentNodeData {
  label: string
  status: 'idle' | 'running' | 'waiting'
  isOrchestrator: boolean
}

const statusColors = {
  idle: 'bg-muted',
  running: 'bg-green-500',
  waiting: 'bg-yellow-500',
}

export const AgentNode = memo(({ data, selected }: NodeProps<AgentNodeData>) => {
  return (
    <div
      className={`px-4 py-3 rounded-xl border-2 transition-all ${
        selected
          ? 'border-primary shadow-lg'
          : 'border-border hover:border-primary/50'
      } ${data.isOrchestrator ? 'bg-primary/5' : 'bg-card'}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-border" />

      <div className="flex items-center gap-2">
        <div className={`w-3 h-3 rounded-full ${statusColors[data.status]}`} />
        <span className="font-medium text-sm">{data.label}</span>
      </div>

      {data.isOrchestrator && (
        <div className="text-xs text-muted-foreground mt-1 text-center">
          Orchestrator
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-border" />
    </div>
  )
})

AgentNode.displayName = 'AgentNode'
