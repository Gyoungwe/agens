import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { providersApi } from '@/api'
import { X, Loader2 } from 'lucide-react'
import type { UpdateProviderRequest } from '@/api/providers'

interface AddProviderDialogProps {
  open: boolean
  onClose: () => void
  mode?: 'create' | 'edit'
  providerId?: string
  initialValues?: {
    id: string
    name: string
    type: 'openai' | 'anthropic'
    model: string
    base_url?: string
    api_key?: string
  }
}

export function AddProviderDialog({ open, onClose, mode = 'create', providerId, initialValues }: AddProviderDialogProps) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    id: initialValues?.id || '',
    name: initialValues?.name || '',
    type: (initialValues?.type || 'openai') as 'openai' | 'anthropic',
    model: initialValues?.model || '',
    base_url: initialValues?.base_url || '',
    api_key: '',
  })
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setForm({
      id: initialValues?.id || '',
      name: initialValues?.name || '',
      type: (initialValues?.type || 'openai') as 'openai' | 'anthropic',
      model: initialValues?.model || '',
      base_url: initialValues?.base_url || '',
      api_key: '',
    })
    setError('')
  }, [open, initialValues?.id, initialValues?.name, initialValues?.type, initialValues?.model, initialValues?.base_url])

  const mutation = useMutation({
    mutationFn: (data: typeof form) => {
      if (mode === 'edit') {
        if (!providerId) throw new Error('Missing provider id')
        const payload: UpdateProviderRequest = {
          name: data.name,
          type: data.type,
          model: data.model,
          base_url: data.base_url,
          api_key: data.api_key,
        }
        return providersApi.updateProvider(providerId, payload)
      }
      return providersApi.addProvider(data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers'] })
      queryClient.invalidateQueries({ queryKey: ['providers-list'] })
      onClose()
      setForm({ id: '', name: '', type: 'openai', model: '', base_url: '', api_key: '' })
      setError('')
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail || (mode === 'edit' ? 'Failed to update provider' : 'Failed to add provider'))
    },
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setForm((prev) => {
      const next = { ...prev, [name]: value }
      if (name === 'name' && !next.id && mode !== 'edit') {
        next.id = value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
      }
      if (name === 'type') {
        if (value === 'anthropic') {
          next.base_url = ''
        } else if (!next.base_url) {
          next.base_url = 'https://api.openai.com/v1'
        }
      }
      return next
    })
  }

  const handleSubmit = () => {
    if (!form.name || !form.model || !form.api_key || (mode !== 'edit' && !form.id)) {
      setError('Please fill in all required fields')
      return
    }
    setError('')
    mutation.mutate(form)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card rounded-xl shadow-xl w-full max-w-md p-6 z-10">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <h3 className="text-lg font-semibold mb-4">{mode === 'edit' ? 'Edit Model' : 'Add Model'}</h3>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Provider Type</label>
            <select
              name="type"
              value={form.type}
              onChange={handleChange}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="openai">OpenAI Compatible</option>
              <option value="anthropic">Anthropic Claude</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              Display Name <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="e.g., My DeepSeek"
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>

          {mode !== 'edit' && (
            <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              Provider ID <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              name="id"
              value={form.id}
              onChange={handleChange}
              placeholder="e.g., my_deepseek"
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 font-mono"
            />
            <p className="text-xs text-muted-foreground mt-1">Unique identifier, auto-generated from name</p>
          </div>
          )}

          <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              Model Name <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              name="model"
              value={form.model}
              onChange={handleChange}
              placeholder={form.type === 'anthropic' ? 'e.g., claude-3-sonnet-20240229' : 'e.g., deepseek-chat'}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>

          {form.type === 'openai' && (
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Base URL</label>
              <input
                type="text"
                name="base_url"
                value={form.base_url}
                onChange={handleChange}
                placeholder="https://api.openai.com/v1"
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 font-mono"
              />
            </div>
          )}

          <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              API Key <span className="text-destructive">*</span>
            </label>
            <input
              type="password"
              name="api_key"
              value={form.api_key}
              onChange={handleChange}
              placeholder={mode === 'edit' ? 'Enter new key to update' : 'sk-...'}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 font-mono"
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-5">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-secondary transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={mutation.isPending || !form.name || !form.model || !form.api_key || (mode !== 'edit' && !form.id)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 cursor-pointer"
          >
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            {mode === 'edit' ? 'Save Changes' : 'Add Model'}
          </button>
        </div>
      </div>
    </div>
  )
}
