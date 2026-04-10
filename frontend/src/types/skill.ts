export interface Skill {
  skill_id: string
  name: string
  description: string
  version: string
  enabled: boolean
  installed_at?: string
  config?: Record<string, unknown>
}

export interface SkillInstallRequest {
  natural_language: string
}

export interface SkillInstallResponse {
  success: boolean
  skill?: Skill
  error?: string
}
