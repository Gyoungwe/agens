import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { approvalsApi } from '@/api'
import { Header } from '@/components/layout'
import { ApprovalCard } from '@/components/approvals/ApprovalCard'
import { useApprovalStore } from '@/store'
import { useWebSocket } from '@/hooks'
import { CheckCircle2 } from 'lucide-react'
import type { Approval } from '@/types'

export function ApprovalsPage() {
  const queryClient = useQueryClient()
  const { setApprovals } = useApprovalStore()

  useWebSocket()

  const { data: approvals, isLoading } = useQuery({
    queryKey: ['approvals'],
    queryFn: async () => {
      const response = await approvalsApi.getApprovals()
      return response.data.approvals
    },
  })

  useQuery({
    queryKey: ['approvals'],
    queryFn: async () => {
      const response = await approvalsApi.getApprovals()
      setApprovals(response.data.approvals)
      return response.data.approvals
    },
    enabled: true,
    refetchInterval: 30000,
  })

  const approveMutation = useMutation({
    mutationFn: (id: string) => approvalsApi.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) => approvalsApi.reject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
  })

  const pendingApprovals = approvals?.filter((a: Approval) => a.status === 'pending')
  const processedApprovals = approvals?.filter((a: Approval) => a.status !== 'pending')

  return (
    <div className="flex flex-col h-full">
      <Header title="Approvals" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="loading-spinner" />
            </div>
          ) : (
            <>
              {/* Pending */}
              <div>
                <h2 className="text-lg font-semibold mb-4">
                  Pending Approvals ({pendingApprovals?.length || 0})
                </h2>
                {pendingApprovals?.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground bg-card rounded-xl border border-border">
                    <CheckCircle2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No pending approvals</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {pendingApprovals?.map((approval: Approval) => (
                      <ApprovalCard
                        key={approval.id}
                        approval={approval}
                        onApprove={() => approveMutation.mutate(approval.id)}
                        onReject={() => rejectMutation.mutate(approval.id)}
                        isApproving={approveMutation.isPending}
                        isRejecting={rejectMutation.isPending}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Processed */}
              {processedApprovals && processedApprovals.length > 0 && (
                <div>
                  <h2 className="text-lg font-semibold mb-4">History</h2>
                  <div className="space-y-3">
                    {processedApprovals.map((approval: Approval) => (
                      <ApprovalCard
                        key={approval.id}
                        approval={approval}
                        isProcessed
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
