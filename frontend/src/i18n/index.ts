import { useLanguageStore, type Language } from '@/store/languageStore'

type Dict = Record<string, string>

const en: Dict = {
  chat: 'Chat',
  research: 'Research',
  channels: 'Channels',
  dashboard: 'Dashboard',
  models: 'Models',
  skills: 'Skills',
  knowledge: 'Knowledge',
  approvals: 'Approvals',
  sessions: 'Sessions',
  agentSettings: 'Agent Settings',
  selectModel: 'Select Model',
  logout: 'Logout',
  user: 'User',
  username: 'Username',
  password: 'Password',
  signIn: 'Sign In',
  signingIn: 'Signing in...',
  invalidCredentials: 'Invalid username or password',
  systemStatus: 'System Status',
  allAgentsOnline: 'All agents online',
}

const zhCN: Dict = {
  chat: '聊天',
  research: '研究',
  channels: '通信',
  dashboard: '仪表盘',
  models: '模型',
  skills: '技能',
  knowledge: '知识库',
  approvals: '审批',
  sessions: '会话',
  agentSettings: '代理设置',
  selectModel: '选择模型',
  logout: '登出',
  user: '用户',
  username: '用户名',
  password: '密码',
  signIn: '登录',
  signingIn: '正在登录...',
  invalidCredentials: '用户名或密码错误',
  systemStatus: '系统状态',
  allAgentsOnline: '所有代理在线',
}

const dictByLanguage: Record<Language, Dict> = {
  en,
  'zh-CN': zhCN,
}

export type TranslationKey = keyof typeof en

export function t(key: TranslationKey): string {
  const lang = useLanguageStore.getState().language
  return translate(lang, key)
}

export function translate(lang: Language, key: TranslationKey): string {
  const dict = dictByLanguage[lang] || en
  return dict[key] || en[key] || key
}
