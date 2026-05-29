/**
 * 配置存储服务
 */

import { StorageService } from './StorageService';
import { StrategyConfig, UserConfig } from './types';

export class ConfigStorage extends StorageService {
  private static readonly STRATEGIES_STORE = 'strategies';
  private static readonly USER_CONFIG_STORE = 'user_config';

  constructor() {
    super({
      name: 'quantmind_config',
      version: 1,
      stores: [
        {
          name: ConfigStorage.STRATEGIES_STORE,
          keyPath: 'id',
          autoIncrement: true,
          indexes: [
            { name: 'name', keyPath: 'name' },
            { name: 'type', keyPath: 'type' },
            { name: 'symbol', keyPath: 'symbol' },
            { name: 'enabled', keyPath: 'enabled' },
            { name: 'type_enabled', keyPath: ['type', 'enabled'] },
          ],
        },
        {
          name: ConfigStorage.USER_CONFIG_STORE,
          keyPath: 'id',
          autoIncrement: true,
          indexes: [
            { name: 'key', keyPath: 'key', unique: true },
            { name: 'category', keyPath: 'category' },
          ],
        },
      ],
    });
  }

  // ========== 策略配置 ==========

  /**
   * 保存策略配置
   */
  async saveStrategy(strategy: Omit<StrategyConfig, 'id'>): Promise<number> {
    const data: StrategyConfig = {
      ...strategy,
      createdAt: strategy.createdAt || Date.now(),
      updatedAt: Date.now(),
    };

    const id = await this.add<StrategyConfig>(ConfigStorage.STRATEGIES_STORE, data);
    return Number(id);
  }

  /**
   * 更新策略配置
   */
  async updateStrategy(id: number, updates: Partial<StrategyConfig>): Promise<void> {
    const existing = await this.get<StrategyConfig>(ConfigStorage.STRATEGIES_STORE, id);

    if (!existing) {
      throw new Error(`策略配置不存在: ${id}`);
    }

    const updated: StrategyConfig = {
      ...existing,
      ...updates,
      id,
      updatedAt: Date.now(),
    };

    await this.update<StrategyConfig>(ConfigStorage.STRATEGIES_STORE, updated);
  }

  /**
   * 获取策略配置
   */
  async getStrategy(id: number): Promise<StrategyConfig | undefined> {
    return this.get<StrategyConfig>(ConfigStorage.STRATEGIES_STORE, id);
  }

  /**
   * 获取所有策略
   */
  async getAllStrategies(): Promise<StrategyConfig[]> {
    return this.getAll<StrategyConfig>(ConfigStorage.STRATEGIES_STORE);
  }

  /**
   * 获取启用的策略
   */
  async getEnabledStrategies(): Promise<StrategyConfig[]> {
    const strategies = await this.getAllStrategies();
    return strategies.filter(s => s.enabled);
  }

  /**
   * 获取指定类型的策略
   */
  async getStrategiesByType(type: string, enabledOnly: boolean = false): Promise<StrategyConfig[]> {
    const strategies = await this.getByIndex<StrategyConfig>(
      ConfigStorage.STRATEGIES_STORE,
      'type',
      type
    );
    return enabledOnly ? strategies.filter(s => s.enabled) : strategies;
  }

  /**
   * 获取指定交易对的策略
   */
  async getStrategiesBySymbol(symbol: string): Promise<StrategyConfig[]> {
    return this.getByIndex<StrategyConfig>(
      ConfigStorage.STRATEGIES_STORE,
      'symbol',
      symbol
    );
  }

  /**
   * 删除策略
   */
  async deleteStrategy(id: number): Promise<void> {
    await this.delete(ConfigStorage.STRATEGIES_STORE, id);
  }

  /**
   * 启用/禁用策略
   */
  async toggleStrategy(id: number, enabled: boolean): Promise<void> {
    await this.updateStrategy(id, { enabled });
  }

  // ========== 用户配置 ==========

  /**
   * 设置配置项
   */
  async setConfig(key: string, value: unknown, category?: string, description?: string): Promise<void> {
    const data: UserConfig = {
      key,
      value,
      category,
      description,
      updatedAt: Date.now(),
    };

    try {
      await this.add<UserConfig>(ConfigStorage.USER_CONFIG_STORE, data);
    } catch (error: unknown) {
      // 如果key已存在，更新它
      const name = (error as { name?: string })?.name;
      if (name === 'ConstraintError') {
        const existing = await this.getConfigByKey(key);
        if (existing && existing.id) {
          const updated = {
            ...existing,
            value,
            category: category ?? existing.category,
            description: description ?? existing.description,
            updatedAt: Date.now(),
          };
          await this.update<UserConfig>(ConfigStorage.USER_CONFIG_STORE, updated);
        }
      } else {
        throw error;
      }
    }
  }

  /**
   * 获取配置项
   */
  async getConfig(key: string, defaultValue?: unknown): Promise<unknown> {
    const config = await this.getConfigByKey(key);
    return config ? config.value : defaultValue;
  }

  /**
   * 通过key获取配置对象
   */
  private async getConfigByKey(key: string): Promise<UserConfig | undefined> {
    const configs = await this.getByIndex<UserConfig>(
      ConfigStorage.USER_CONFIG_STORE,
      'key',
      key
    );
    return configs[0];
  }

  /**
   * 获取分类下的所有配置
   */
  async getConfigsByCategory(category: string): Promise<UserConfig[]> {
    return this.getByIndex<UserConfig>(
      ConfigStorage.USER_CONFIG_STORE,
      'category',
      category
    );
  }

  /**
   * 获取所有配置
   */
  async getAllConfigs(): Promise<UserConfig[]> {
    return this.getAll<UserConfig>(ConfigStorage.USER_CONFIG_STORE);
  }

  /**
   * 删除配置项
   */
  async deleteConfig(key: string): Promise<void> {
    const config = await this.getConfigByKey(key);
    if (config && config.id) {
      await this.delete(ConfigStorage.USER_CONFIG_STORE, config.id);
    }
  }

  /**
   * 批量设置配置
   */
  async setConfigs(configs: Record<string, unknown>, category?: string): Promise<void> {
    for (const [key, value] of Object.entries(configs)) {
      await this.setConfig(key, value, category);
    }
  }

  /**
   * 导出所有配置（用于备份）
   */
  async exportConfig(): Promise<{
    strategies: StrategyConfig[];
    userConfig: UserConfig[];
    exportTime: number;
  }> {
    const strategies = await this.getAllStrategies();
    const userConfig = await this.getAllConfigs();

    return {
      strategies,
      userConfig,
      exportTime: Date.now(),
    };
  }

  /**
   * 导入配置（用于恢复）
   */
  async importConfig(data: {
    strategies?: StrategyConfig[];
    userConfig?: UserConfig[];
  }): Promise<{ strategiesImported: number; configsImported: number }> {
    let strategiesImported = 0;
    let configsImported = 0;

    // 导入策略
    if (data.strategies) {
      for (const strategy of data.strategies) {
        const strategyData = { ...strategy } as Omit<StrategyConfig, 'id'>;
        delete (strategyData as Partial<StrategyConfig>).id;
        await this.saveStrategy(strategyData);
        strategiesImported++;
      }
    }

    // 导入用户配置
    if (data.userConfig) {
      for (const config of data.userConfig) {
        await this.setConfig(config.key, config.value, config.category, config.description);
        configsImported++;
      }
    }

    return { strategiesImported, configsImported };
  }
}
