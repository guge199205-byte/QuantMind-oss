/**
 * 安全的日志工具类，用于修复EPIPE错误
 * 在Electron应用中提供安全的日志输出机制
 */

class SafeLogger {
  private static instance: SafeLogger;
  private isEnabled: boolean = true;

  private constructor() {}

  static getInstance(): SafeLogger {
    if (!SafeLogger.instance) {
      SafeLogger.instance = new SafeLogger();
    }
    return SafeLogger.instance;
  }

  /**
   * 启用或禁用日志
   */
  setEnabled(enabled: boolean): void {
    this.isEnabled = enabled;
  }

  /**
   * 安全的日志输出，捕获EPIPE错误
   */
  private safeLog(level: 'log' | 'info' | 'warn' | 'error', ...args: any[]): void {
    if (!this.isEnabled) return;

    try {
      const originalConsole = console[level] || console.log;
      originalConsole.apply(console, args);
    } catch (error: any) {
      // 忽略EPIPE错误，通常发生在进程关闭时
      if (error.code === 'EPIPE') {
        // 静默处理，避免进程崩溃
        return;
      }

      // 对于其他错误，尝试静默处理
      try {
        // 尝试输出到原始console.error
        const originalError = console.error;
        originalError(`[SafeLogger Error in ${level}]:`, error);
      } catch {
        // 完全静默，避免递归错误
      }
    }
  }

  log(...args: any[]): void {
    this.safeLog('log', ...args);
  }

  info(...args: any[]): void {
    this.safeLog('info', ...args);
  }

  warn(...args: any[]): void {
    this.safeLog('warn', ...args);
  }

  error(...args: any[]): void {
    this.safeLog('error', ...args);
  }

  /**
   * 开发模式下日志，生产模式下自动静默
   */
  devLog(...args: any[]): void {
    if (process.env.NODE_ENV === 'development' || process.env.VITE_DEV === '1') {
      this.log(...args);
    }
  }

  /**
   * 带时间戳的日志
   */
  timeLog(...args: any[]): void {
    const timestamp = new Date().toISOString();
    this.log(`[${timestamp}]`, ...args);
  }

  /**
   * 带时间戳的错误日志
   */
  timeError(...args: any[]): void {
    const timestamp = new Date().toISOString();
    this.error(`[${timestamp}]`, ...args);
  }
}

// 导出单例实例
const logger = SafeLogger.getInstance();

// 在开发环境下，也可以直接替换全局console方法（可选）
if (process.env.NODE_ENV === 'development' || process.env.VITE_DEV === '1') {
  // 可选：在开发环境下替换全局console
  // console.log = (...args) => logger.log(...args);
  // console.warn = (...args) => logger.warn(...args);
  // console.error = (...args) => logger.error(...args);
}

export default logger;
