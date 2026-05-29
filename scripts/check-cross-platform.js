#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const root = process.cwd();
const electronRoot = path.join(root, 'electron');

function exists(p) {
  return fs.existsSync(p);
}

function check(requiredPath, description, required = true) {
  const ok = exists(requiredPath);
  const marker = ok ? 'OK' : (required ? 'FAIL' : 'WARN');
  console.log(`[${marker}] ${description}: ${requiredPath}`);
  return ok || !required;
}

const checks = [];

checks.push(check(path.join(root, 'package.json'), '根 package.json'));
checks.push(check(path.join(root, 'package-lock.json'), '根 package-lock.json'));
checks.push(check(path.join(electronRoot, 'package.json'), 'Electron package.json'));
checks.push(check(path.join(electronRoot, 'build', 'icon.ico'), 'Windows 图标 icon.ico'));
checks.push(check(path.join(root, 'backend', 'services', 'ai_ide'), 'AI-IDE 后端目录'));

if (process.platform === 'darwin') {
  checks.push(check(path.join(electronRoot, 'build', 'icon.icns'), 'macOS 图标 icon.icns'));
} else {
  check(path.join(electronRoot, 'build', 'icon.icns'), 'macOS 图标 icon.icns', false);
}

if (checks.every(Boolean)) {
  console.log('\n跨平台基础检查通过。');
  process.exit(0);
}

console.error('\n跨平台基础检查失败，请先修复 FAIL 项。');
process.exit(1);
