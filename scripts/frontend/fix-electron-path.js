const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * 自动修复 Electron 可执行文件路径脚本
 * 
 * 作用：解决在不同平台（Windows/Mac/Linux）开发时，
 * node_modules/electron/path.txt 可能被错误配置的问题。
 */

function fixElectronPath() {
  const platform = os.platform();
  let electronExecPath = '';

  switch (platform) {
    case 'win32':
      electronExecPath = 'electron.exe';
      break;
    case 'darwin':
      electronExecPath = 'Electron.app/Contents/MacOS/Electron';
      break;
    case 'linux':
      electronExecPath = 'electron';
      break;
    default:
      console.log(`[FixPath] 不支持的平台: ${platform}`);
      return;
  }

  const rootDir = path.join(__dirname, '..', '..');
  const searchPaths = [
    path.join(rootDir, 'node_modules/electron/path.txt'),
    path.join(rootDir, 'electron/node_modules/electron/path.txt')
  ];

  let fixed = false;
  for (const filePath of searchPaths) {
    if (fs.existsSync(filePath)) {
      try {
        fs.writeFileSync(filePath, electronExecPath);
        console.log(`[FixPath] 已成功修复 ${filePath} -> ${electronExecPath}`);
        fixed = true;
      } catch (err) {
        console.error(`[FixPath] 写入失败 ${filePath}:`, err.message);
      }
    }
  }

  if (!fixed) {
    console.log('[FixPath] 未找到 electron/path.txt，跳过修复（可能尚未安装依赖）');
  }
}

fixElectronPath();
