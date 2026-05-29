/**
 * @deprecated 此文件已废弃，不再使用。
 * 自动更新逻辑已集中至 electron/main.ts 的 setupAutoUpdater() 函数中。
 * 请勿在新代码中引用此文件，后续版本将删除。
 *
 * 自动更新服务
 * 使用 electron-updater 实现自动更新功能
 */

import { autoUpdater } from 'electron-updater';
import { BrowserWindow, dialog } from 'electron';
import log from 'electron-log';

/**
 * 更新配置
 */
interface UpdateConfig {
  checkOnStart: boolean;
  checkInterval: number; // 毫秒
  autoDownload: boolean;
  autoInstall: boolean;
}

/**
 * 默认配置
 */
const defaultConfig: UpdateConfig = {
  checkOnStart: true,
  checkInterval: 60 * 60 * 1000, // 1小时
  autoDownload: true,
  autoInstall: false // 需要用户确认
};

/**
 * 自动更新管理器
 */
export class UpdateManager {
  private config: UpdateConfig;
  private checkTimer: NodeJS.Timeout | null = null;
  private mainWindow: BrowserWindow | null = null;

  constructor(config?: Partial<UpdateConfig>) {
    this.config = { ...defaultConfig, ...config };
    this.setupLogger();
    this.setupAutoUpdater();
  }

  /**
   * 设置日志
   */
  private setupLogger(): void {
    // 配置electron-log
    log.transports.file.level = 'info';
    autoUpdater.logger = log;
  }

  /**
   * 设置autoUpdater
   */
  private setupAutoUpdater(): void {
    // 配置自动下载
    autoUpdater.autoDownload = this.config.autoDownload;
    autoUpdater.autoInstallOnAppQuit = this.config.autoInstall;

    // 设置事件监听器
    this.setupEventListeners();
  }

  /**
   * 设置事件监听器
   */
  private setupEventListeners(): void {
    // 检查更新时
    autoUpdater.on('checking-for-update', () => {
      log.info('Checking for update...');
      this.sendStatusToWindow('checking-for-update');
    });

    // 发现新版本
    autoUpdater.on('update-available', (info) => {
      log.info('Update available:', info);
      this.sendStatusToWindow('update-available', info);

      this.showNotification(
        '发现新版本',
        `新版本 ${info.version} 可用，正在下载...`
      );
    });

    // 没有新版本
    autoUpdater.on('update-not-available', (info) => {
      log.info('Update not available:', info);
      this.sendStatusToWindow('update-not-available', info);
    });

    // 下载进度
    autoUpdater.on('download-progress', (progressObj) => {
      log.info(`Download progress: ${progressObj.percent}%`);
      this.sendStatusToWindow('download-progress', progressObj);
    });

    // 下载完成
    autoUpdater.on('update-downloaded', (info) => {
      log.info('Update downloaded:', info);
      this.sendStatusToWindow('update-downloaded', info);

      this.showUpdateDialog(info);
    });

    // 错误处理
    autoUpdater.on('error', (error) => {
      log.error('Update error:', error);
      this.sendStatusToWindow('update-error', { message: error.message });

      this.showNotification(
        '更新失败',
        '检查更新时发生错误，请稍后重试'
      );
    });
  }

  /**
   * 设置主窗口
   */
  setMainWindow(window: BrowserWindow): void {
    this.mainWindow = window;
  }

  /**
   * 发送状态到渲染进程
   */
  private sendStatusToWindow(status: string, data?: any): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send('update-status', { status, data });
    }
  }

  /**
   * 显示通知
   */
  private showNotification(title: string, body: string): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send('show-notification', { title, body });
    }
  }

  /**
   * 显示更新对话框
   */
  private async showUpdateDialog(info: any): Promise<void> {
    if (!this.mainWindow || this.mainWindow.isDestroyed()) {
      return;
    }

    const { response } = await dialog.showMessageBox(this.mainWindow, {
      type: 'info',
      title: '发现新版本',
      message: `新版本 ${info.version} 已下载完成`,
      detail: '是否立即重启应用并安装更新？',
      buttons: ['立即安装', '稍后安装'],
      defaultId: 0,
      cancelId: 1
    });

    if (response === 0) {
      // 立即安装
      setImmediate(() => {
        autoUpdater.quitAndInstall(false, true);
      });
    }
  }

  /**
   * 检查更新
   */
  async checkForUpdates(): Promise<void> {
    try {
      await autoUpdater.checkForUpdates();
    } catch (error) {
      log.error('Check for updates failed:', error);
    }
  }

  /**
   * 启动定期检查
   */
  startPeriodicCheck(): void {
    if (this.checkTimer) {
      return;
    }

    // 启动时检查
    if (this.config.checkOnStart) {
      setTimeout(() => {
        this.checkForUpdates();
      }, 5000); // 延迟5秒启动
    }

    // 定期检查
    this.checkTimer = setInterval(() => {
      this.checkForUpdates();
    }, this.config.checkInterval);

    log.info('Periodic update check started');
  }

  /**
   * 停止定期检查
   */
  stopPeriodicCheck(): void {
    if (this.checkTimer) {
      clearInterval(this.checkTimer);
      this.checkTimer = null;
      log.info('Periodic update check stopped');
    }
  }

  /**
   * 手动下载更新
   */
  async downloadUpdate(): Promise<void> {
    try {
      await autoUpdater.downloadUpdate();
    } catch (error) {
      log.error('Download update failed:', error);
    }
  }

  /**
   * 退出并安装
   */
  quitAndInstall(): void {
    autoUpdater.quitAndInstall(false, true);
  }

  /**
   * 获取当前版本
   */
  getCurrentVersion(): string {
    return autoUpdater.currentVersion.version;
  }

  /**
   * 设置更新源
   */
  setFeedURL(url: string): void {
    autoUpdater.setFeedURL({
      provider: 'generic',
      url
    });
  }
}

// 导出单例
export const updateManager = new UpdateManager();
