
const fs = require('fs');
const path = require('path');

const dirsToRemove = [
  'dist',
  'dist-react',
  'dist-electron',
  'node_modules/.vite',
  '.vite'
];

const filesToRemove = [
  'electron/main.js',
  'electron/preload.js',
  'electron/*.js.map',
  'tsconfig.tsbuildinfo'
];

console.log('🧹 Cleaning build artifacts...');

// Remove directories
dirsToRemove.forEach(dir => {
  const dirPath = path.join(__dirname, '..', dir);
  if (fs.existsSync(dirPath)) {
    console.log(`Removing directory: ${dir}`);
    fs.rmSync(dirPath, { recursive: true, force: true });
  }
});

// Remove specific files
filesToRemove.forEach(file => {
  const filePath = path.join(__dirname, '..', file);
  if (fs.existsSync(filePath)) {
    console.log(`Removing file: ${file}`);
    fs.unlinkSync(filePath);
  }
});

// Remove all .js.map files in electron directory
const electronDir = path.join(__dirname, '..', 'electron');
if (fs.existsSync(electronDir)) {
  const files = fs.readdirSync(electronDir);
  files.forEach(file => {
    if (file.endsWith('.js.map')) {
      const filePath = path.join(electronDir, file);
      console.log(`Removing source map: ${file}`);
      fs.unlinkSync(filePath);
    }
  });
}

console.log('✅ Cleanup complete!');
