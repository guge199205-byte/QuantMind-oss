import loader from '@monaco-editor/loader';

// Force Monaco to load from local bundled assets instead of the default CDN.
// This avoids the editor being stuck on "Loading..." when cdn.jsdelivr.net is blocked/offline.
//
// We copy `node_modules/monaco-editor/min/vs` to `electron/public/monaco/vs` via
// `scripts/copy-monaco-assets.js` (run on postinstall/build).
// Respect Vite base when the app is served from a sub-path in dev/preview.
// In production we use relative base ("./") so this resolves to the bundled directory.
const viteBase = (import.meta as any).env?.BASE_URL || './';
const baseUrl = new URL(viteBase, window.location.href).toString();
const vsPath = new URL('monaco/vs', baseUrl).toString().replace(/\/$/, '');

loader.config({
  paths: {
    vs: vsPath,
  },
});
