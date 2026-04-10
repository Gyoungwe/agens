import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { approvalsApi } from '@/api'
import { Header } from '@/components/layout'
import { ApprovalCard } from '@/components/approvals/ApprovalCard'
import { useApprovalStore } from '@/store'
import { useWebSocket } from '@/hooks'
import { CheckCircle2, Shield } from 'lucide-react'
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
        <div className="max-w-3xl mx-auto space-y-8">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
          ) : (
            <>
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cta/20 to-primary/20 flex items-center justify-center">
                    <Shield className="w-5 h-5 text-cta" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">Pending Approvals</h2>
                    <p className="text-xs text-muted-foreground font-mono">
                      {pendingApprovals?.length || 0} items require your approval
                    </p>
                  </div>
                </div>
                {pendingApprovals?.length === 0 ? (
                  <div className="glass-card rounded-2xl p-8 text-center">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-success/20 to-success/10 flex items-center justify-center">
                      <CheckCircle2 className="w-8 h-8 text-success" />
                    </div>
                    <h3 className="text-lg font-semibold mb-1">All Caught Up</h3>
                    <p className="text-sm text-muted-foreground">No pending approvals</p>
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

              {processedApprovals && processedApprovals.length > 0 && (
                <div>
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-muted/30 to-muted/10 flex items-center justify-center">
                      <CheckCircle2 className="w-5 h-5 text-muted-foreground" />
                    </div>
                    <h2 className="text-lg font-semibold">History</h2>
                  </div>
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
