import { useQuery } from '@tanstack/react-query'

export function ModelSelector() {
  const { data: providers } = useQuery({
    queryKey: ['providers'],
    queryFn: async () => {
      const res = await fetch('/api/providers')
      return res.json()
    },
  })

  return (
    <select className="text-sm bg-secondary border border-border rounded-lg px-3 py-1.5">
      {providers?.map((p: { id: string; model: string }) => (
        <option key={p.id} value={p.id}>
          {p.model}
        </option>
      ))}
    </select>
  )
}
