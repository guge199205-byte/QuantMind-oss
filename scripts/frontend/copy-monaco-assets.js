const fs = require('fs');
const path = require('path');

/**
 * 复制 Monaco Editor 资源脚本
 * 
 * 作用：将 node_modules 中的 Monaco Editor 核心资源复制到 public 目录，
 * 以便在不依赖外部 CDN 的情况下在本地加载编辑器。
 */

function copyMonacoAssets() {
  const rootDir = path.join(__dirname, '..', '..');
  
  // 源路径：从根目录的 node_modules 查找（workspaces 模式下依赖在根目录）
  let srcDir = path.join(rootDir, 'node_modules/monaco-editor/min/vs');
  if (!fs.existsSync(srcDir)) {
    srcDir = path.join(rootDir, 'electron/node_modules/monaco-editor/min/vs');
  }

  // 目标路径：必须在 electron/public 目录下
  const destDir = path.join(rootDir, 'electron/public/monaco/vs');

  if (!fs.existsSync(srcDir)) {
    console.log('[Monaco] 未找到 monaco-editor 资源，跳过复制（请先运行 npm install）');
    return;
  }

  // 确保目标目录存在
  if (!fs.existsSync(path.dirname(destDir))) {
    fs.mkdirSync(path.dirname(destDir), { recursive: true });
  }

  // 递归复制函数
  function copyRecursive(src, dest) {
    const stats = fs.statSync(src);
    if (stats.isDirectory()) {
      if (!fs.existsSync(dest)) {
        fs.mkdirSync(dest, { recursive: true });
      }
      fs.readdirSync(src).forEach(child => {
        copyRecursive(path.join(src, child), path.join(dest, child));
      });
    } else {
      fs.copyFileSync(src, dest);
    }
  }

  try {
    console.log(`[Monaco] 正在从 ${srcDir} 复制资源到 ${destDir}...`);
    copyRecursive(srcDir, destDir);
    console.log('[Monaco] 资源复制成功！');
  } catch (err) {
    console.error('[Monaco] 资源复制失败:', err.message);
  }
}

copyMonacoAssets();
