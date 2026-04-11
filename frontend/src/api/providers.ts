import client from './client'

export interface Provider {
  id: string
  name: string
  model: string
  active: boolean
}

export interface ProviderHealth {
  provider_id: string
  healthy: boolean
  active: boolean
}

export interface AddProviderRequest {
  id: string
  name: string
  type: 'openai' | 'anthropic'
  model: string
  base_url?: string
  api_key: string
}

export interface UpdateProviderRequest {
  name: string
  type: 'openai' | 'anthropic'
  model: string
  base_url?: string
  api_key: string
}

export const providersApi = {
  getProviders: () =>
    client.get<Provider[]>('/providers'),

  addProvider: (data: AddProviderRequest) =>
    client.post<{ success: boolean; provider_id: string }>('/providers', data),

  updateProvider: (providerId: string, data: UpdateProviderRequest) =>
    client.put<{ success: boolean; provider_id: string }>(`/providers/${providerId}`, data),

  deleteProvider: (providerId: string) =>
    client.delete<{ success: boolean }>(`/providers/${providerId}`),

  getCurrentProvider: () =>
    client.get<{ id: string; name: string; model: string }>('/providers/current'),

  getHealth: (providerId?: string) =>
    client.get<ProviderHealth>('/providers/health', {
      params: providerId ? { provider_id: providerId } : undefined,
    }),

  switchProvider: (providerId: string) =>
    client.post<{ success: boolean; provider: string }>(`/providers/${providerId}/use`),
}
