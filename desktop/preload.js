const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // 应用信息
  getAppPath: () => ipcRenderer.invoke('get-app-path'),

  // 对话框
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),

  // 事件监听
  onNewSession: (callback) => ipcRenderer.on('new-session', callback),
  onOpenSettings: (callback) => ipcRenderer.on('open-settings', callback),

  // 移除监听
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
});
