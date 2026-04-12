import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { skillsApi } from '@/api'
import { Header } from '@/components/layout'
import { SkillCard } from '@/components/skills/SkillCard'
import { InstallDialog } from '@/components/skills/InstallDialog'
import { Wrench, Sparkles } from 'lucide-react'
import type { Skill } from '@/types'

export function SkillsPage() {
  const [installDialogOpen, setInstallDialogOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: skillsData, isLoading } = useQuery({
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
          <div className="flex justify-between items-center mb-8">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <Wrench className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Manage agent skills and capabilities
                </p>
                <p className="text-xs text-muted-foreground/60 font-mono">
                  {skillsData?.length || 0} skills installed
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setInstallDialogOpen(true)}
                className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-primary to-primary/80 text-primary-foreground hover:shadow-lg hover:shadow-primary/25 hover:scale-105 transition-all duration-200 cursor-pointer"
              >
                <Sparkles className="w-4 h-4" />
                Install Skill
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
          ) : skillsData?.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <Wrench className="w-10 h-10 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">No Skills Installed</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Install a skill to enhance your agents capabilities
              </p>
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
