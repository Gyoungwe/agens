import client from './client'

export interface ChannelsConfigResponse {
  wecom: {
    configured: boolean
    token_masked: string
  }
  feishu: {
    configured: boolean
    app_id_masked: string
  }
}

export interface ChannelsStatusResponse {
  wecom_enabled: boolean
  feishu_enabled: boolean
  runtime_ready: boolean
  active_channel_sessions: number
  wecom_webhook: string
  feishu_webhook: string
}

export interface SaveChannelsConfigRequest {
  wecom?: {
    bot_token?: string
  }
  feishu?: {
    bot_app_id?: string
  }
}

export const channelsApi = {
  getConfig: () => client.get<ChannelsConfigResponse>('/channels/config'),
  saveConfig: (data: SaveChannelsConfigRequest) =>
    client.put<{ success: boolean; message: string }>('/channels/config', data),
  getStatus: () => client.get<ChannelsStatusResponse>('/channels/status'),
}
