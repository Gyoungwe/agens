import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { skillsApi } from '@/api'
import { Header } from '@/components/layout'
import { SkillCard } from '@/components/skills/SkillCard'
import { InstallDialog } from '@/components/skills/InstallDialog'
import { Plus, RefreshCw } from 'lucide-react'
import type { Skill } from '@/types'

export function SkillsPage() {
  const [installDialogOpen, setInstallDialogOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: skillsData, isLoading, refetch } = useQuery({
    queryKey: ['skills'],
    queryFn: async () => {
      const response = await skillsApi.getSkills()
      return response.data.skills
    },
  })

  const uninstallMutation = useMutation({
    mutationFn: (skillId: string) => skillsApi.uninstallSkill(skillId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
    },
  })

  return (
    <div className="flex flex-col h-full">
      <Header title="Skills" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-6">
            <p className="text-muted-foreground">
              Manage agent skills and capabilities
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => refetch()}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-secondary transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
              <button
                onClick={() => setInstallDialogOpen(true)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Install Skill
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="loading-spinner" />
            </div>
          ) : skillsData?.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <div className="text-4xl mb-4">🛠️</div>
              <h3 className="text-lg font-medium mb-2">No skills installed</h3>
              <p className="text-sm">Install a skill to get started</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {skillsData?.map((skill: Skill) => (
                <SkillCard
                  key={skill.skill_id}
                  skill={skill}
                  onUninstall={() => uninstallMutation.mutate(skill.skill_id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <InstallDialog
        open={installDialogOpen}
        onClose={() => setInstallDialogOpen(false)}
      />
    </div>
  )
}
