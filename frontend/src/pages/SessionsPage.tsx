import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/api'
import { Header } from '@/components/layout'
import { ConfirmDialog } from '@/components/shared'
import { useState } from 'react'
import { MessageSquare, Trash2, Clock } from 'lucide-react'

export function SessionsPage() {
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: sessionsData, isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: async () => {
      const response = await chatApi.getSessions()
      return response.data.sessions
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => chatApi.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      setDeleteConfirm(null)
    },
  })

  return (
    <div className="flex flex-col h-full">
      <Header title="Sessions" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="loading-spinner" />
            </div>
          ) : sessionsData?.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <div className="text-4xl mb-4">💬</div>
              <h3 className="text-lg font-medium mb-2">No sessions</h3>
              <p className="text-sm">Start a new chat to create a session</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sessionsData?.map((session: {
                session_id: string;
                title: string;
                status: string;
                message_count: number;
                created_at: string;
              }) => (
                <div
                  key={session.session_id}
                  className="bg-card rounded-xl border border-border p-4 hover:border-primary/50 transition-colors"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
                      <MessageSquare className="w-5 h-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium truncate">
                        {session.title || 'New Conversation'}
                      </h3>
                      <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(session.created_at).toLocaleString()}
                        </span>
                        <span>{session.message_count} messages</span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs ${
                            session.status === 'active'
                              ? 'bg-green-500/10 text-green-600'
                              : 'bg-muted text-muted-foreground'
                          }`}
                        >
                          {session.status}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => setDeleteConfirm(session.session_id)}
                      className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={!!deleteConfirm}
        onClose={() => setDeleteConfirm(null)}
        onConfirm={() => deleteConfirm && deleteMutation.mutate(deleteConfirm)}
        title="Delete Session"
        description="Are you sure you want to delete this session? This action cannot be undone."
        confirmText="Delete"
        variant="destructive"
      />
    </div>
  )
}
