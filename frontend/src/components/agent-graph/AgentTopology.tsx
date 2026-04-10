import { useMemo } from 'react'
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow'
import type { Node, Edge } from 'reactflow'
import 'reactflow/dist/style.css'
import { AgentNode } from './AgentNode'
import type { Agent } from '@/types'

const nodeTypes = {
  agent: AgentNode,
}

interface AgentTopologyProps {
  agents: Agent[]
}

export function AgentTopology({ agents }: AgentTopologyProps) {
  const initialNodes: Node[] = useMemo(() => {
    const centerX = 250
    const centerY = 150
    const radius = 120

    const nodes: Node[] = [
      {
        id: 'orchestrator',
        type: 'agent',
        position: { x: centerX, y: centerY },
        data: {
          label: 'Orchestrator',
          status: 'idle',
          isOrchestrator: true,
        },
      },
    ]

    const workerAgents = agents.filter((a) => a.agent_id !== 'orchestrator')
    workerAgents.forEach((agent, index) => {
      const angle = ((index + 1) * 2 * Math.PI) / (workerAgents.length + 1)
      nodes.push({
        id: agent.agent_id,
        type: 'agent',
        position: {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        },
        data: {
          label: agent.name || agent.agent_id,
          status: agent.status,
          isOrchestrator: false,
        },
      })
    })

    return nodes
  }, [agents])

  const initialEdges: Edge[] = useMemo(() => {
    return agents
      .filter((a) => a.agent_id !== 'orchestrator')
      .map((agent) => ({
        id: `orchestrator-${agent.agent_id}`,
        source: 'orchestrator',
        target: agent.agent_id,
        type: 'smoothstep',
        animated: agent.status === 'running',
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
        style: { stroke: '#94a3b8', strokeWidth: 2 },
      }))
  }, [agents])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useMemo(() => {
    setNodes(initialNodes)
    setEdges(initialEdges)
  }, [initialNodes, initialEdges, setNodes, setEdges])

  return (
    <div className="w-full h-full bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Controls />
        <MiniMap />
        <Background />
      </ReactFlow>
    </div>
  )
}
