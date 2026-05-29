// Electron API 类型声明
declare global {
  interface Window {
    electronAPI: {
      // 应用信息
      getAppVersion: () => string;

      // 窗口控制
      minimizeWindow: () => Promise<void>;
      maximizeWindow: () => Promise<void>;
      closeWindow: () => Promise<void>;

      // 系统信息
      getPlatform: () => string;
      getSystemVersion: () => string;
      getLocale: () => string;

      // 通知功能
      showNotification: (title: string, body: string) => Promise<void>;

      // 导出功能
      exportSaveFile: (options: any) => Promise<any>;

      // AI-IDE 目录选择与路径打开
      selectDirectory: () => Promise<any>;
      ensureDefaultAIIDEWorkspace: () => Promise<{ success: boolean; path?: string; readmeFileName?: string; usedFallback?: boolean; warning?: string; error?: string }>;
      openPath: (path: string) => Promise<any>;
      openExternal: (url: string) => Promise<{ success: boolean; error?: string }>;
      checkPython: () => Promise<{ installed: boolean; version?: string; command?: string; executable?: string }>;
      getAIIDEConfig: () => Promise<any>;
      updateAIIDEConfig: (config: any) => Promise<{ success: boolean }>;
      selectPython: () => Promise<{ canceled: boolean; path?: string; error?: string }>;
      getAIIDERuntimeStatus: () => Promise<{
        pythonPath: string;
        pythonExists: boolean;
        coreReady: boolean;
        missingModules: string[];
        bundleProfile?: 'bare' | 'core' | 'full' | 'unknown';
        bundleDetectedBy?: string;
        installCommands: { core: string; full: string };
      }>;
      restartAIIDEBackend: () => Promise<{ success: boolean }>;

      // 菜单事件监听器
      onMenuExportData: (callback: () => void) => () => void;
      onMenuPerformanceMonitor: (callback: () => void) => () => void;

      // 自动更新
      onUpdateDownloaded: (callback: (info: any) => void) => () => void;
      onUpdateAvailable: (callback: (info: { version: string; releaseNotes?: string }) => void) => () => void;
      onUpdateDownloadProgress: (callback: (progress: { percent: number; transferred: number; total: number }) => void) => () => void;
      onUpdateError: (callback: (err: { message: string }) => void) => () => void;
      checkForUpdates: () => Promise<void>;
      installUpdate: () => Promise<void>;
    };

  }
}

export { };
