import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Header } from '@/components/layout'
import { AddProviderDialog } from '@/components/providers/AddProviderDialog'
import { providersApi } from '@/api'
import { Plus, Trash2, Bot, CheckCircle2, XCircle } from 'lucide-react'
import type { Provider } from '@/api/providers'

export function ProvidersPage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Provider | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Provider | null>(null)
  const queryClient = useQueryClient()

  const { data: providers = [], isLoading } = useQuery({
    queryKey: ['providers-list'],
    queryFn: async () => {
      const res = await providersApi.getProviders()
      return res.data
    },
  })
  const [errorHint, setErrorHint] = useState<string | null>(null)

  const switchMutation = useMutation({
    mutationFn: (id: string) => providersApi.switchProvider(id),
    onSuccess: () => {
      setErrorHint(null)
      queryClient.invalidateQueries({ queryKey: ['providers-list'] })
    },
    onError: (e: unknown) => {
      setErrorHint(e instanceof Error ? e.message : 'Failed to switch model')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => providersApi.deleteProvider(id),
    onSuccess: () => {
      setErrorHint(null)
      queryClient.invalidateQueries({ queryKey: ['providers-list'] })
      setDeleteTarget(null)
    },
    onError: (e: unknown) => {
      setErrorHint(e instanceof Error ? e.message : 'Failed to delete model')
    },
  })

  return (
    <div className="flex flex-col h-full">
      <Header title="Models" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          {errorHint && (
            <div className="mb-4 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm flex items-center justify-between gap-2">
              <span>{errorHint}</span>
              <button
                onClick={() => {
                  setErrorHint(null)
                  queryClient.invalidateQueries({ queryKey: ['providers-list'] })
                }}
                className="px-2 py-1 text-xs rounded border border-destructive/40 hover:bg-destructive/20"
              >
                Retry
              </button>
            </div>
          )}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <Bot className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Manage AI model providers
                </p>
                <p className="text-xs text-muted-foreground/60 font-mono">
                  {providers.length} models configured
                </p>
              </div>
            </div>
            <button
              onClick={() => setDialogOpen(true)}
              className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-primary to-primary/80 text-primary-foreground hover:shadow-lg hover:shadow-primary/25 hover:scale-105 transition-all duration-200 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Add Model
            </button>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
          ) : providers.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <Bot className="w-10 h-10 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">No Models</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Add your first model provider to get started
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {providers.map((provider) => (
                <div
                  key={provider.id}
                  className={`glass-card rounded-xl p-4 transition-all duration-200 ${
                    provider.active ? 'ring-2 ring-primary/50' : ''
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      provider.active
                        ? 'bg-gradient-to-br from-primary to-cta text-white'
                        : 'bg-gradient-to-br from-primary/20 to-cta/20 text-primary'
                    }`}>
                      <Bot className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-foreground">{provider.name}</h3>
                        {provider.active ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-success/10 text-success">
                            <CheckCircle2 className="w-3 h-3" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
                            <XCircle className="w-3 h-3" />
                            Inactive
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground font-mono">
                        <span>ID: {provider.id}</span>
                        <span>Model: {provider.model}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => setEditTarget(provider)}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary hover:bg-secondary/80 text-foreground transition-colors cursor-pointer"
                      >
                        Edit
                      </button>
                      {!provider.active && (
                        <button
                          onClick={() => switchMutation.mutate(provider.id)}
                          disabled={switchMutation.isPending}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary hover:bg-secondary/80 text-foreground transition-colors cursor-pointer disabled:opacity-50"
                        >
                          Switch
                        </button>
                      )}
                      <button
                        onClick={() => setDeleteTarget(provider)}
                        disabled={provider.active}
                        className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors disabled:opacity-30 cursor-pointer"
                        title={provider.active ? 'Cannot delete active provider' : 'Delete'}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AddProviderDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />

      <AddProviderDialog
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        mode="edit"
        providerId={editTarget?.id}
        initialValues={
          editTarget
            ? {
                id: editTarget.id,
                name: editTarget.name,
                type: 'openai',
                model: editTarget.model,
                base_url: 'https://api.openai.com/v1',
              }
            : undefined
        }
      />

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/50" onClick={() => setDeleteTarget(null)} />
          <div className="relative bg-card rounded-xl shadow-xl w-full max-w-sm p-6 z-10">
            <h3 className="text-lg font-semibold mb-2">Delete Model</h3>
            <p className="text-sm text-muted-foreground mb-5">
              Are you sure you want to delete <strong>{deleteTarget.name}</strong>? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-secondary transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deleteTarget.id)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50 cursor-pointer"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
