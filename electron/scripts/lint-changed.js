const { execSync, spawnSync } = require('child_process');

function getChangedFiles() {
  const cmd = 'git diff --name-only --diff-filter=ACMRTUXB HEAD';
  const output = execSync(cmd, { encoding: 'utf-8' }).trim();
  if (!output) return [];
  return output
    .split('\n')
    .map((f) => f.trim())
    .filter(Boolean)
    .filter((f) => f.startsWith('electron/src/'))
    .filter((f) => f.endsWith('.ts') || f.endsWith('.tsx'))
    .map((f) => f.replace(/^electron\//, ''));
}

function main() {
  const files = getChangedFiles();
  if (files.length === 0) {
    console.log('[lint:changed] No changed TS/TSX files in electron/src, skip.');
    return;
  }
  console.log('[lint:changed] Files:', files.join(', '));

  const result = spawnSync(
    'eslint',
    ['--max-warnings=0', ...files],
    { stdio: 'inherit', shell: true }
  );

  process.exit(result.status ?? 1);
}

main();
