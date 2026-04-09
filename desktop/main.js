const { app, BrowserWindow, Menu, Tray, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let tray = null;
let apiProcess = null;

const isDev = process.argv.includes('--dev');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#1e1e2e',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 15, y: 15 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 创建应用菜单
  const menuTemplate = [
    {
      label: '文件',
      submenu: [
        {
          label: '新会话',
          accelerator: 'CmdOrCtrl+N',
          click: () => mainWindow.webContents.send('new-session'),
        },
        { type: 'separator' },
        {
          label: '设置',
          accelerator: 'CmdOrCtrl+,',
          click: () => mainWindow.webContents.send('open-settings'),
        },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: '窗口',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        { type: 'separator' },
        {
          label: '始终置顶',
          type: 'checkbox',
          checked: false,
          click: (menuItem) => {
            mainWindow.setAlwaysOnTop(menuItem.checked);
          },
        },
      ],
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '关于',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '关于 Multi-Agent 系统',
              message: 'Multi-Agent 智能协作系统',
              detail: '版本: 0.02\n\n一个基于 LLM 的多智能体协作系统。',
            });
          },
        },
        {
          label: '打开日志目录',
          click: () => {
            shell.openPath(path.join(app.getPath('userData'), 'logs'));
          },
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(menuTemplate);
  Menu.setApplicationMenu(menu);

  // 加载页面
  if (isDev) {
    mainWindow.loadURL('http://localhost:8000');
  } else {
    const apiPath = path.join(__dirname, '../api/main.py');
    const webPath = path.join(__dirname, '../web/index.html');

    // 启动 API 服务器
    apiProcess = spawn('python3', ['-m', 'uvicorn', 'api.main:app', '--host', '0.0.0.0', '--port', '8000'], {
      cwd: path.join(__dirname, '..'),
      detached: false,
      stdio: 'pipe',
    });

    apiProcess.stdout.on('data', (data) => {
      console.log(`API: ${data}`);
    });

    apiProcess.stderr.on('data', (data) => {
      console.error(`API Error: ${data}`);
    });

    // 等待 API 启动
    setTimeout(() => {
      mainWindow.loadURL('http://localhost:8000');
    }, 3000);

    // 应用关闭时停止 API
    app.on('before-quit', () => {
      if (apiProcess) {
        apiProcess.kill();
      }
    });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // 创建系统托盘
  createTray();
}

function createTray() {
  const iconPath = path.join(__dirname, 'icon.png');
  const fs = require('fs');

  // 如果图标不存在，跳过托盘创建
  if (!fs.existsSync(iconPath)) {
    console.log('Tray icon not found, skipping tray creation');
    return;
  }

  try {
    tray = new Tray(iconPath);

    const contextMenu = Menu.buildFromTemplate([
      {
        label: '显示窗口',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      {
        label: '新会话',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.webContents.send('new-session');
          }
        },
      },
      { type: 'separator' },
      {
        label: '退出',
        click: () => {
          app.quit();
        },
      },
    ]);

    tray.setToolTip('Multi-Agent 智能协作系统');
    tray.setContextMenu(contextMenu);

    tray.on('click', () => {
      if (mainWindow) {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    });
  } catch (e) {
    console.log('Failed to create tray:', e);
  }
}

// IPC 通信
ipcMain.handle('get-app-path', () => {
  return app.getPath('userData');
});

ipcMain.handle('show-save-dialog', async (event, options) => {
  return dialog.showSaveDialog(mainWindow, options);
});

ipcMain.handle('show-open-dialog', async (event, options) => {
  return dialog.showOpenDialog(mainWindow, options);
});

// 应用生命周期
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// 快捷键全局注册
global.shortcut = {
  newSession: 'CmdOrCtrl+N',
  commandPalette: 'CmdOrCtrl+K',
};
