import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/api'
import { Header } from '@/components/layout'
import { ConfirmDialog } from '@/components/shared'
import { useState } from 'react'
import { MessageSquare, Trash2, Clock, ScrollText } from 'lucide-react'

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
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <ScrollText className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Chat history and conversations
                </p>
                <p className="text-xs text-muted-foreground/60 font-mono">
                  {sessionsData?.length || 0} sessions
                </p>
              </div>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
          ) : sessionsData?.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <MessageSquare className="w-10 h-10 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">No Sessions Yet</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Start a new conversation to create your first session
              </p>
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
                  className="glass-card rounded-xl p-4 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center flex-shrink-0">
                      <MessageSquare className="w-6 h-6 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold truncate text-foreground">
                        {session.title || 'New Conversation'}
                      </h3>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1 font-mono">
                          <Clock className="w-3 h-3" />
                          {new Date(session.created_at).toLocaleString()}
                        </span>
                        <span className="font-mono">{session.message_count} messages</span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            session.status === 'active'
                              ? 'bg-success/10 text-success'
                              : 'bg-muted text-muted-foreground'
                          }`}
                        >
                          {session.status}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => setDeleteConfirm(session.session_id)}
                      className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors cursor-pointer"
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
