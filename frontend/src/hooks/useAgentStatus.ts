import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { agentsApi } from '@/api'
import { useAgentStore } from '@/store'

export function useAgentStatus() {
  const { setAgents } = useAgentStore()

  const query = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await agentsApi.getAgents()
      return response.data.agents
    },
    refetchInterval: 10000,
  })

  useEffect(() => {
    if (query.data) {
      setAgents(query.data)
    }
  }, [query.data, setAgents])

  return query
}
