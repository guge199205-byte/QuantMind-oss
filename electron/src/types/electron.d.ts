export { };

declare global {
  interface Window {
    electronAPI: {
      getAppVersion: () => string;
      minimizeWindow: () => Promise<void>;
      maximizeWindow: () => Promise<void>;
      closeWindow: () => Promise<void>;
      getPlatform: () => string;
      getSystemVersion: () => string;
      getLocale: () => string;
      showNotification: (title: string, body: string) => Promise<void>;
      exportSaveFile: (options: any) => Promise<any>;
      openPath: (path: string) => Promise<any>;
      openExternal: (url: string) => Promise<{ success: boolean; error?: string }>;
      createUser: (user: { username: string; email?: string; password: string; displayName?: string }) => Promise<any>;
      verifyLogin: (cred: { username: string; password: string }) => Promise<any>;
      getUser: (opts: { username: string }) => Promise<any>;
      listUsers: () => Promise<any>;
      onMenuExportData: (callback: () => void) => () => void;
      onMenuPerformanceMonitor: (callback: () => void) => () => void;
      onUpdateDownloaded: (callback: (info: any) => void) => () => void;
      onUpdateAvailable: (callback: (info: { version: string; releaseNotes?: string }) => void) => () => void;
      onUpdateDownloadProgress: (callback: (progress: { percent: number; transferred: number; total: number }) => void) => () => void;
      onUpdateError: (callback: (err: { message: string }) => void) => () => void;
      checkForUpdates: () => Promise<void>;
      installUpdate: () => Promise<void>;
      keepAliveAIIDEBackend: () => Promise<{ running: boolean }>;
      waitAIIDEBackendReady: () => Promise<{ ready: boolean }>;
    };
  }
}
