import { Check, X, Clock } from 'lucide-react'
import type { Approval } from '@/types/event'

interface ApprovalCardProps {
  approval: Approval
  onApprove?: () => void
  onReject?: () => void
  isApproving?: boolean
  isRejecting?: boolean
  isProcessed?: boolean
}

export function ApprovalCard({
  approval,
  onApprove,
  onReject,
  isApproving,
  isRejecting,
  isProcessed,
}: ApprovalCardProps) {
  const isWorkflowEvolution = approval.kind === 'workflow_retrospective'

  return (
    <div
      className={`bg-card rounded-xl border-l-4 p-4 ${
        approval.status === 'pending'
          ? 'border-l-yellow-500'
          : approval.status === 'approved'
          ? 'border-l-green-500'
          : 'border-l-red-500 opacity-60'
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium">
            Agent <span className="text-primary">{approval.agent_id}</span>{' '}
            {isWorkflowEvolution ? 'submitted a workflow evolution record' : 'requests skill installation'}
          </h3>
          <p className="text-sm font-mono text-muted-foreground">
            {approval.skill_name || approval.skill_id}
          </p>
        </div>
        <span
          className={`px-2 py-1 rounded-full text-xs font-medium ${
            approval.status === 'pending'
              ? 'bg-yellow-500/10 text-yellow-600'
              : approval.status === 'approved'
              ? 'bg-green-500/10 text-green-600'
              : 'bg-red-500/10 text-red-600'
          }`}
        >
          {approval.status}
        </span>
      </div>

      <div className="bg-muted rounded-lg p-3 mb-4">
        <p className="text-sm text-muted-foreground mb-1">Reason</p>
        <p className="text-sm">{approval.reason}</p>
      </div>

      {isWorkflowEvolution && (
        <div className="bg-muted rounded-lg p-3 mb-4 space-y-2">
          <div>
            <p className="text-sm text-muted-foreground mb-1">Workflow Summary</p>
            <p className="text-sm whitespace-pre-wrap break-words">{approval.summary || 'No summary'}</p>
          </div>
          <div className="text-xs text-muted-foreground font-mono">
            provider={approval.provider_id || 'default'} · scope={approval.scope_id || 'default'}
          </div>
          {approval.workflow_trace_id && (
            <div className="text-xs text-muted-foreground font-mono">
              trace={approval.workflow_trace_id}
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="w-3 h-3" />
          {new Date(approval.created_at).toLocaleString()}
        </div>

        {isProcessed ? (
          <span className="text-xs text-muted-foreground">
            Processed {approval.updated_at ? new Date(approval.updated_at).toLocaleString() : ''}
          </span>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={onReject}
              disabled={isRejecting}
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg border border-destructive/50 text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
            >
              <X className="w-4 h-4" />
              Reject
            </button>
            <button
              onClick={onApprove}
              disabled={isApproving}
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              <Check className="w-4 h-4" />
              Approve
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
