/**
 * 用户偏好设置服务
 */

export type Theme = 'light' | 'dark' | 'auto';
export type Language = 'zh-CN' | 'en-US';
export type Layout = 'default' | 'compact' | 'wide';

export interface UserPreferences {
  theme: Theme;
  language: Language;
  layout: Layout;
  notifications: {
    desktop: boolean;
    sound: boolean;
    email: boolean;
  };
  chart: {
    defaultInterval: string;
    defaultType: string;
    showVolume: boolean;
    showGrid: boolean;
  };
  trading: {
    confirmOrders: boolean;
    defaultLeverage: number;
    riskPerTrade: number;
  };
  display: {
    fontSize: number;
    compactMode: boolean;
    showSidebar: boolean;
  };
}

export class PreferencesService {
  private static STORAGE_KEY = 'user_preferences';
  private preferences: UserPreferences;
  private listeners: Set<(prefs: UserPreferences) => void> = new Set();

  constructor() {
    this.preferences = this.loadPreferences();
    this.applyTheme();
  }

  /**
   * 获取偏好设置
   */
  getPreferences(): UserPreferences {
    return { ...this.preferences };
  }

  /**
   * 更新偏好设置
   */
  updatePreferences(updates: Partial<UserPreferences>): void {
    const normalizedUpdates = { ...updates };
    if (normalizedUpdates.theme && normalizedUpdates.theme !== 'light') {
      normalizedUpdates.theme = 'light';
    }
    this.preferences = { ...this.preferences, ...normalizedUpdates };
    this.savePreferences();
    this.notifyListeners();

    // 应用主题变化
    if (normalizedUpdates.theme) {
      this.applyTheme();
    }

    // 应用字体大小变化
    if (updates.display?.fontSize) {
      this.applyFontSize(updates.display.fontSize);
    }
  }

  /**
   * 重置为默认设置
   */
  resetToDefaults(): void {
    this.preferences = this.getDefaultPreferences();
    this.savePreferences();
    this.notifyListeners();
    this.applyTheme();
  }

  /**
   * 获取主题
   */
  getTheme(): Theme {
    return this.preferences.theme;
  }

  /**
   * 设置主题
   */
  setTheme(_theme: Theme): void {
    this.updatePreferences({ theme: 'light' });
  }

  /**
   * 获取语言
   */
  getLanguage(): Language {
    return this.preferences.language;
  }

  /**
   * 设置语言
   */
  setLanguage(language: Language): void {
    this.updatePreferences({ language });
  }

  /**
   * 导出设置
   */
  exportPreferences(): string {
    return JSON.stringify(this.preferences, null, 2);
  }

  /**
   * 导入设置
   */
  importPreferences(json: string): boolean {
    try {
      const prefs = JSON.parse(json);
      // 验证设置格式
      if (this.validatePreferences(prefs)) {
        this.preferences = prefs;
        this.savePreferences();
        this.notifyListeners();
        this.applyTheme();
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to import preferences:', error);
      return false;
    }
  }

  /**
   * 添加监听器
   */
  addListener(listener: (prefs: UserPreferences) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * 应用主题
   */
  private applyTheme(): void {
    const theme = this.getEffectiveTheme();
    document.documentElement.setAttribute('data-theme', theme);

    // 更新meta theme-color
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      metaTheme.setAttribute('content', theme === 'dark' ? '#1e1e1e' : '#ffffff');
    }
  }

  /**
   * 获取实际主题（处理auto）
   */
  private getEffectiveTheme(): 'light' | 'dark' {
    return 'light';
  }

  /**
   * 应用字体大小
   */
  private applyFontSize(fontSize: number): void {
    document.documentElement.style.fontSize = `${fontSize}px`;
  }

  /**
   * 加载偏好设置
   */
  private loadPreferences(): UserPreferences {
    try {
      const stored = localStorage.getItem(PreferencesService.STORAGE_KEY);
      if (stored) {
        const prefs = JSON.parse(stored);
        // 合并默认值以处理新增的设置项
        return { ...this.getDefaultPreferences(), ...prefs, theme: 'light' };
      }
    } catch (error) {
      console.error('Failed to load preferences:', error);
    }
    return this.getDefaultPreferences();
  }

  /**
   * 保存偏好设置
   */
  private savePreferences(): void {
    try {
      localStorage.setItem(
        PreferencesService.STORAGE_KEY,
        JSON.stringify(this.preferences)
      );
    } catch (error) {
      console.error('Failed to save preferences:', error);
    }
  }

  /**
   * 通知监听器
   */
  private notifyListeners(): void {
    this.listeners.forEach(listener => {
      try {
        listener(this.getPreferences());
      } catch (error) {
        console.error('Error in preferences listener:', error);
      }
    });
  }

  /**
   * 验证偏好设置
   */
  private validatePreferences(prefs: any): boolean {
    if (!prefs || typeof prefs !== 'object') return false;

    // 基本验证
    const requiredKeys = ['theme', 'language', 'layout', 'notifications', 'chart', 'trading', 'display'];
    return requiredKeys.every(key => key in prefs);
  }

  /**
   * 获取默认偏好设置
   */
  private getDefaultPreferences(): UserPreferences {
    return {
      theme: 'light',
      language: 'zh-CN',
      layout: 'default',
      notifications: {
        desktop: true,
        sound: true,
        email: false
      },
      chart: {
        defaultInterval: '1h',
        defaultType: 'candlestick',
        showVolume: true,
        showGrid: true
      },
      trading: {
        confirmOrders: true,
        defaultLeverage: 1,
        riskPerTrade: 0.02
      },
      display: {
        fontSize: 14,
        compactMode: false,
        showSidebar: true
      }
    };
  }
}

// 单例
export const preferencesService = new PreferencesService();
