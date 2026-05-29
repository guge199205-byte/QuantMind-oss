const { spawnSync } = require('child_process');

const PHASES = {
  '1': [
    'src/pages',
    'src/services',
    'src/config',
    'src/constants',
    'src/contexts',
    'src/providers',
  ],
  '2': [
    'src/features',
    'src/store',
    'src/stores',
    'src/state',
  ],
  '3': [
    'src/components',
    'src/hooks',
    'src/shared',
    'src/types',
    'src/utils',
    'src/i18n',
    'src/main',
    'src/monaco',
  ],
};

function parseArgs(argv) {
  const args = { phase: '1', list: false };
  for (const raw of argv) {
    if (raw === '--list') {
      args.list = true;
      continue;
    }
    if (raw.startsWith('--phase=')) {
      args.phase = raw.split('=')[1];
    }
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const targets = PHASES[args.phase];
  if (!targets) {
    console.error(
      `[lint:phase] Invalid phase "${args.phase}". Valid values: ${Object.keys(PHASES).join(', ')}`
    );
    process.exit(2);
  }

  console.log(`[lint:phase] phase=${args.phase}`);
  console.log(`[lint:phase] targets=${targets.join(', ')}`);

  if (args.list) {
    process.exit(0);
  }

  const result = spawnSync(
    'eslint',
    ['--max-warnings=0', '--ext', '.ts,.tsx', ...targets],
    { stdio: 'inherit', shell: true }
  );
  process.exit(result.status ?? 1);
}

main();
