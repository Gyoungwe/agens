import { memo } from 'react'
import type { EdgeProps } from 'reactflow'
import { getBezierPath } from 'reactflow'

export const MessageEdge = memo(({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  animated,
  style,
}: EdgeProps) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={style}
      />
      {animated && (
        <path
          d={edgePath}
          fill="none"
          className="animated"
          strokeDasharray="5,5"
          strokeWidth={2}
        />
      )}
    </>
  )
})

MessageEdge.displayName = 'MessageEdge'
