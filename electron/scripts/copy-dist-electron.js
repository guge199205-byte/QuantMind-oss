#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const src = path.join(root, 'dist-react');
const dest = path.join(root, 'dist-electron', 'dist-react');

async function copy() {
  try {
    if (!fs.existsSync(src)) {
      console.error('Source folder does not exist:', src);
      process.exit(1);
    }

    if (fs.existsSync(dest)) {
      await fs.promises.rm(dest, { recursive: true, force: true });
    }

    // Use fs.cp when available (Node 16+), otherwise fallback to manual copy
    if (fs.promises && fs.promises.cp) {
      await fs.promises.cp(src, dest, { recursive: true });
    } else {
      await copyRecursive(src, dest);
    }

    console.log(`Copied ${src} -> ${dest}`);
  } catch (err) {
    console.error('Failed to copy dist-react to dist-electron:', err);
    process.exit(1);
  }
}

async function copyRecursive(srcDir, destDir) {
  await fs.promises.mkdir(destDir, { recursive: true });
  const entries = await fs.promises.readdir(srcDir, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(srcDir, entry.name);
    const destPath = path.join(destDir, entry.name);
    if (entry.isDirectory()) {
      await copyRecursive(srcPath, destPath);
    } else if (entry.isSymbolicLink()) {
      const link = await fs.promises.readlink(srcPath);
      await fs.promises.symlink(link, destPath);
    } else {
      await fs.promises.copyFile(srcPath, destPath);
    }
  }
}

copy();
