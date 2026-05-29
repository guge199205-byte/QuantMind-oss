// 简化的Electron主进程文件，用于诊断问题
console.log('[SIMPLE] Starting simplified Electron main process...');

try {
  const electron = require('electron');
  console.log('[SIMPLE] Electron module loaded successfully');
  console.log('[SIMPLE] Available APIs:', Object.keys(electron));

  const { app, BrowserWindow } = electron;
  console.log('[SIMPLE] App:', typeof app);
  console.log('[SIMPLE] BrowserWindow:', typeof BrowserWindow);

  if (!app) {
    throw new Error('app is undefined');
  }

  if (!app.whenReady) {
    throw new Error('app.whenReady is undefined');
  }

  let mainWindow = null;

  function createWindow() {
    console.log('[SIMPLE] Creating window...');

    mainWindow = new BrowserWindow({
      width: 1200,
      height: 800,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true
      }
    });

    console.log('[SIMPLE] Window created');

    // 尝试加载开发服务器
    mainWindow.loadURL('http://127.0.0.1:3000')
      .then(() => {
        console.log('[SIMPLE] Dev server loaded successfully');
        mainWindow.webContents.openDevTools({ mode: 'detach' });
      })
      .catch(err => {
        console.error('[SIMPLE] Failed to load dev server:', err);

        // 回退到本地文件
        const path = require('path');
        const indexPath = path.join(__dirname, '../dist-react/index.html');

        console.log('[SIMPLE] Trying to load local file:', indexPath);

        const fs = require('fs');
        if (fs.existsSync(indexPath)) {
          mainWindow.loadFile(indexPath)
            .then(() => {
              console.log('[SIMPLE] Local file loaded successfully');
              mainWindow.webContents.openDevTools({ mode: 'detach' });
            })
            .catch(err => {
              console.error('[SIMPLE] Failed to load local file:', err);
            });
        } else {
          console.error('[SIMPLE] Local file does not exist:', indexPath);
        }
      });

    mainWindow.on('closed', () => {
      console.log('[SIMPLE] Window closed');
      mainWindow = null;
    });
  }

  app.whenReady()
    .then(() => {
      console.log('[SIMPLE] App ready');
      createWindow();
    })
    .catch(err => {
      console.error('[SIMPLE] App ready error:', err);
    });

  app.on('window-all-closed', () => {
    console.log('[SIMPLE] All windows closed');
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });

  console.log('[SIMPLE] Setup complete');

} catch (error) {
  console.error('[SIMPLE] Error:', error);
  console.error('[SIMPLE] Stack:', error.stack);
  process.exit(1);
}
