#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

// 启动Vite开发服务器
console.log('🚀 Starting Vite development server...');
const viteProcess = spawn('npm', ['run', 'dev:react'], {
  stdio: 'inherit',
  shell: true,
  cwd: __dirname + '/..'
});

// 等待Vite服务器启动后启动Electron
viteProcess.on('data', (data) => {
  const output = data.toString();
  if (output.includes('Local:') || output.includes('ready')) {
    console.log('✅ Vite server is ready, starting Electron...');

    // 延迟启动Electron，确保Vite服务器完全启动
    setTimeout(() => {
      const electronProcess = spawn('electron', ['.'], {
        stdio: 'inherit',
        shell: true,
        cwd: __dirname + '/..',
        env: { ...process.env, VITE_DEV: '1' }
      });

      electronProcess.on('close', (code) => {
        console.log(`Electron process exited with code ${code}`);
        viteProcess.kill();
        process.exit(code);
      });
    }, 2000);
  }
});

viteProcess.on('close', (code) => {
  console.log(`Vite process exited with code ${code}`);
  process.exit(code);
});

// 处理进程信号
process.on('SIGINT', () => {
  viteProcess.kill();
  process.exit();
});

process.on('SIGTERM', () => {
  viteProcess.kill();
  process.exit();
});
