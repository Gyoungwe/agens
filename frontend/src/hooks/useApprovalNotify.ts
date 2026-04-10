import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { approvalsApi } from '@/api'
import { useApprovalStore } from '@/store'

export function useApprovalNotify() {
  const queryClient = useQueryClient()
  const { setApprovals } = useApprovalStore()

  const query = useQuery({
    queryKey: ['approvals'],
    queryFn: async () => {
      const response = await approvalsApi.getApprovals()
      return response.data.approvals
    },
    refetchInterval: 30000,
  })

  useEffect(() => {
    if (query.data) {
      setApprovals(query.data)
    }
  }, [query.data, setApprovals])

  const refetch = () => {
    queryClient.invalidateQueries({ queryKey: ['approvals'] })
  }

  return { ...query, refetch }
}
