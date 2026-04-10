import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { skillsApi } from '@/api'
import { X, Loader2 } from 'lucide-react'

interface InstallDialogProps {
  open: boolean
  onClose: () => void
}

export function InstallDialog({ open, onClose }: InstallDialogProps) {
  const [naturalLanguage, setNaturalLanguage] = useState('')
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (text: string) => skillsApi.installSkill({ natural_language: text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
      setNaturalLanguage('')
      onClose()
    },
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card rounded-xl shadow-xl w-full max-w-lg p-6 z-10">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="w-4 h-4" />
        </button>

        <h3 className="text-lg font-semibold mb-4">Install Skill</h3>

        <p className="text-sm text-muted-foreground mb-4">
          Describe the skill you want to install in natural language. The system
          will analyze your request and install the appropriate Claude skill.
        </p>

        <textarea
          value={naturalLanguage}
          onChange={(e) => setNaturalLanguage(e.target.value)}
          placeholder="e.g., I need a skill that can search the web for real-time information"
          rows={4}
          className="w-full px-4 py-3 rounded-lg border border-input bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 mb-4"
        />

        {mutation.error && (
          <p className="text-sm text-destructive mb-4">
            {mutation.error.message || 'Failed to install skill'}
          </p>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-secondary transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate(naturalLanguage)}
            disabled={!naturalLanguage.trim() || mutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Install
          </button>
        </div>
      </div>
    </div>
  )
}
