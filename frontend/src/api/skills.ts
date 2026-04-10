import client from './client'
import type { Skill, SkillInstallRequest } from '@/types'

export const skillsApi = {
  getSkills: () =>
    client.get<{ skills: Skill[] }>('/skills/'),

  getSkill: (skillId: string) =>
    client.get<{ skill: Skill }>(`/skills/${skillId}`),

  installSkill: (data: SkillInstallRequest) =>
    client.post<{ success: boolean; skill?: Skill; error?: string }>('/skills/install', data),

  uninstallSkill: (skillId: string) =>
    client.delete<{ success: boolean }>(`/skills/${skillId}`),

  reloadSkills: () =>
    client.post<{ success: boolean }>('/skills/reload'),
}
