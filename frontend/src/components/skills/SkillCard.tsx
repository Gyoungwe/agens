import { Wrench, Trash2 } from 'lucide-react'
import type { Skill } from '@/types'

interface SkillCardProps {
  skill: Skill
  onUninstall: () => void
}

export function SkillCard({ skill, onUninstall }: SkillCardProps) {
  return (
    <div className="bg-card rounded-xl border border-border p-4 hover:border-primary/50 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
            <Wrench className="w-5 h-5 text-muted-foreground" />
          </div>
          <div>
            <h3 className="font-medium">{skill.name || skill.skill_id}</h3>
            <p className="text-xs text-muted-foreground font-mono">
              v{skill.version}
            </p>
          </div>
        </div>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
            skill.enabled
              ? 'bg-green-500/10 text-green-600'
              : 'bg-muted text-muted-foreground'
          }`}
        >
          {skill.enabled ? 'Enabled' : 'Disabled'}
        </span>
      </div>

      <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
        {skill.description || 'No description available'}
      </p>

      <div className="flex justify-end">
        <button
          onClick={onUninstall}
          className="flex items-center gap-1 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          Uninstall
        </button>
      </div>
    </div>
  )
}
