# QuantMind 前端跨平台配置指南

本文档说明 QuantMind Electron 前端如何支持 Windows、Linux 和 macOS 三大平台。

## 跨平台兼容性总览

### ✅ 已实现的跨平台支持

#### 1. **开发环境**
- ✅ 使用 `cross-env` 实现跨平台环境变量设置
- ✅ 使用 `concurrently` 同时运行多个命令
- ✅ 使用 `wait-on` 跨平台端口监听
- ✅ 自动修复 Electron 可执行文件路径（`scripts/fix-electron-path.js`）

#### 2. **构建配置**
- ✅ **Windows**: NSIS 安装包 + 便携版（x64）
- ✅ **macOS**: DMG + ZIP（x64 + arm64/Apple Silicon）
- ✅ **Linux**: AppImage + Deb 包（x64）

#### 3. **代码层面**
- ✅ 使用 Node.js `path` 模块处理文件路径
- ✅ 避免硬编码路径分隔符
- ✅ 使用 `process.platform` 检测操作系统

---

## 常见问题与解决方案

### 问题 1：Electron 启动失败（Windows）

**症状**：
```
Error: spawn E:\code\quantmind\node_modules\electron\dist\Electron.app\Contents\MacOS\Electron ENOENT
```

**原因**：`node_modules\electron\path.txt` 被错误配置为 macOS 路径。

**解决方案**：
```bash
# 自动修复
npm run postinstall

# 或手动运行
node scripts/fix-electron-path.js
```

### 问题 2：npm 警告 `Unknown config "electron_mirror"`

**症状**：
```
npm warn Unknown env config "electron-mirror"
npm warn Unknown project config "electron_mirror"
```

**原因**：npm v9+ 废弃了 `.npmrc` 中的 `electron_mirror` 配置。

**解决方案**：
已在 `.npmrc` 中移除，如需配置镜像，使用环境变量：

```bash
# Windows
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/

# Linux/Mac
export ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
```

### 问题 3：缺少 `cross-env` 依赖

**症状**：
```
'cross-env' is not recognized as an internal or external command
```

**解决方案**：
```bash
cd electron
npm install cross-env --save
```

---

## 平台特定配置

### Windows

**开发环境**：
- Node.js 18+
- Visual Studio Build Tools（可选，用于 native 模块）

**启动**：
```bash
npm run dev
```

**构建**：
```bash
npm run build:package
# 输出: dist/QuantMind Dashboard-Setup-1.0.0.exe
# 输出: dist/QuantMind Dashboard-1.0.0.exe (便携版)
```

---

### macOS

**开发环境**：
- Node.js 18+
- Xcode Command Line Tools

**启动**：
```bash
npm run dev
```

**构建**：
```bash
npm run build:package
# 输出: dist/QuantMind Dashboard-1.0.0-x64.dmg
# 输出: dist/QuantMind Dashboard-1.0.0-arm64.dmg (Apple Silicon)
# 输出: dist/QuantMind Dashboard-1.0.0-x64.zip
# 输出: dist/QuantMind Dashboard-1.0.0-arm64.zip
```

**注意事项**：
- 需要 Apple Developer ID 进行代码签名和公证
- 修改 `electron-builder.yml` 中的 `notarize.teamId`

---

### Linux

**开发环境**：
- Node.js 18+
- 构建工具: `build-essential`

**启动**：
```bash
npm run dev
```

**构建**：
```bash
npm run build:package
# 输出: dist/QuantMind Dashboard-1.0.0.AppImage
# 输出: dist/QuantMind Dashboard-1.0.0-amd64.deb
```

**依赖安装**（Debian/Ubuntu）：
```bash
sudo apt-get install gconf2 gconf-service libnotify4 libappindicator1 libxtst6 libnss3
```

---

## 自动化脚本

### `scripts/fix-electron-path.js`

**作用**：自动检测并修复 Electron 可执行文件路径。

**触发时机**：
- 每次 `npm install` 后自动运行（通过 `postinstall` hook）
- 可手动运行：`node scripts/fix-electron-path.js`

**平台映射**：
```javascript
{
  win32: 'electron.exe',
  darwin: 'Electron.app/Contents/MacOS/Electron',
  linux: 'electron'
}
```

---

## 构建配置文件

### `electron/package.json`
- 开发和构建脚本
- 平台特定的 electron-builder 配置

### `electron-builder.yml`（推荐使用）
- 集中管理所有平台的构建配置
- 包含代码签名、自动更新等高级配置

---

## 验证跨平台兼容性

### 开发环境验证
```bash
# 1. 清理依赖
rm -rf node_modules electron/node_modules

# 2. 重新安装
npm install

# 3. 验证修复脚本
node scripts/fix-electron-path.js

# 4. 启动开发服务器
npm run dev
```

### 构建验证

**Windows**：
```bash
npm run build:package
# 检查 dist/ 目录是否生成 .exe 文件
```

**macOS**：
```bash
npm run build:package
# 检查 dist/ 目录是否生成 .dmg 和 .zip 文件
```

**Linux**：
```bash
npm run build:package
# 检查 dist/ 目录是否生成 .AppImage 和 .deb 文件
```

---

## CI/CD 配置建议

### GitHub Actions 示例

```yaml
name: Build Multi-Platform

on: [push, pull_request]

jobs:
  build:
    strategy:
      matrix:
        os: [windows-latest, macos-latest, ubuntu-latest]

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm install

      - name: Build
        run: npm run build:package

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: dist-${{ matrix.os }}
          path: electron/dist/
```

---

## 已知限制

1. **macOS 代码签名**：需要 Apple Developer 账户和证书
2. **Linux 系统托盘**：某些 Linux 发行版可能不支持系统托盘图标
3. **ARM64 支持**：
   - macOS: ✅ 完全支持（Apple Silicon）
   - Windows: ⚠️ 实验性支持（Windows on ARM）
   - Linux: ⚠️ 部分支持（需额外配置）

---

## 最佳实践

### 1. 路径处理
```typescript
// ❌ 错误：硬编码路径分隔符
const filePath = 'C:\\Users\\data\\file.txt';

// ✅ 正确：使用 path 模块
import path from 'path';
const filePath = path.join(app.getPath('userData'), 'data', 'file.txt');
```

### 2. 平台检测
```typescript
import { platform } from 'os';

if (platform() === 'win32') {
  // Windows 特定代码
} else if (platform() === 'darwin') {
  // macOS 特定代码
} else if (platform() === 'linux') {
  // Linux 特定代码
}
```

### 3. 环境变量
```typescript
// ❌ 错误：直接使用 Windows 语法
// SET NODE_ENV=production

// ✅ 正确：使用 cross-env
// package.json
{
  "scripts": {
    "start": "cross-env NODE_ENV=production electron ."
  }
}
```

---

## 更新日志

- **2026-01-18**：
  - ✅ 实现自动 Electron 路径修复脚本
  - ✅ 移除废弃的 `electron_mirror` 配置
  - ✅ 完善跨平台构建配置
  - ✅ 添加 Linux 平台支持

---

## 相关资源

- [Electron Builder 文档](https://www.electron.build/)
- [Electron API 文档](https://www.electronjs.org/docs/latest/)
- [Node.js Path 模块](https://nodejs.org/api/path.html)
- [cross-env 文档](https://github.com/kentcdodds/cross-env)
