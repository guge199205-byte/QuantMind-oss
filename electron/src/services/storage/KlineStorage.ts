/**
 * K线数据存储服务
 */

import { StorageService } from './StorageService';
import { KlineData, RangeQuery, BatchResult } from './types';

export class KlineStorage extends StorageService {
  private static readonly STORE_NAME = 'klines';

  constructor() {
    super({
      name: 'quantmind_market_data',
      version: 1,
      stores: [
        {
          name: KlineStorage.STORE_NAME,
          keyPath: 'id',
          autoIncrement: true,
          indexes: [
            { name: 'symbol', keyPath: 'symbol' },
            { name: 'interval', keyPath: 'interval' },
            { name: 'timestamp', keyPath: 'timestamp' },
            { name: 'symbol_interval', keyPath: ['symbol', 'interval'] },
            { name: 'symbol_interval_timestamp', keyPath: ['symbol', 'interval', 'timestamp'], unique: true },
          ],
        },
      ],
    });
  }

  /**
   * 保存K线数据
   */
  async saveKline(kline: Omit<KlineData, 'id' | 'createdAt'>): Promise<number> {
    const data: KlineData = {
      ...kline,
      createdAt: Date.now(),
    };

    try {
      const id = await this.add<KlineData>(KlineStorage.STORE_NAME, data);
      return Number(id);
    } catch (error: unknown) {
      // 如果是唯一性约束冲突，尝试更新
      const name = (error as { name?: string })?.name;
      if (name === 'ConstraintError') {
        return this.updateKline(kline);
      }
      throw error;
    }
  }

  /**
   * 批量保存K线数据（带去重）
   */
  async saveKlinesBatch(klines: Omit<KlineData, 'id' | 'createdAt'>[]): Promise<BatchResult> {
    const result: BatchResult = {
      success: 0,
      failed: 0,
      errors: [],
    };

    // 按时间戳去重
    const uniqueKlines = this.deduplicateKlines(klines);

    for (const kline of uniqueKlines) {
      try {
        await this.saveKline(kline);
        result.success++;
      } catch (error) {
        result.failed++;
        result.errors.push(error as Error);
      }
    }

    return result;
  }

  /**
   * 更新K线数据
   */
  private async updateKline(kline: Omit<KlineData, 'id' | 'createdAt'>): Promise<number> {
    // 先查找现有记录
    const existing = await this.getByIndex<KlineData>(
      KlineStorage.STORE_NAME,
      'symbol_interval_timestamp',
      [kline.symbol, kline.interval, kline.timestamp]
    );

    if (existing.length > 0) {
      const updated = {
        ...existing[0],
        ...kline,
      };
      const id = await this.update<KlineData>(KlineStorage.STORE_NAME, updated);
      return Number(id);
    }

    throw new Error('未找到要更新的K线记录');
  }

  /**
   * 获取指定时间范围的K线
   */
  async getKlinesByTimeRange(
    symbol: string,
    interval: string,
    query: RangeQuery
  ): Promise<KlineData[]> {
    this.ensureDb();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(KlineStorage.STORE_NAME, 'readonly');
      const store = transaction.objectStore(KlineStorage.STORE_NAME);
      const index = store.index('symbol_interval_timestamp');

      // 创建范围查询
      const range = IDBKeyRange.bound(
        [symbol, interval, query.start],
        [symbol, interval, query.end]
      );

      const request = index.getAll(range, query.limit);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 获取最新的N条K线
   */
  async getLatestKlines(symbol: string, interval: string, limit: number = 100): Promise<KlineData[]> {
    const allKlines = await this.getByIndex<KlineData>(
      KlineStorage.STORE_NAME,
      'symbol_interval',
      [symbol, interval]
    );

    // 按时间戳降序排序
    return allKlines
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, limit);
  }

  /**
   * 获取指定数量的历史K线
   */
  async getHistoricalKlines(
    symbol: string,
    interval: string,
    count: number,
    endTime?: number
  ): Promise<KlineData[]> {
    const end = endTime || Date.now();

    // 根据interval计算时间范围
    const intervalMs = this.intervalToMilliseconds(interval);
    const start = end - (intervalMs * count);

    return this.getKlinesByTimeRange(symbol, interval, { start, end, limit: count });
  }

  /**
   * 删除过期的K线数据
   */
  async deleteExpiredKlines(symbol: string, interval: string, beforeTimestamp: number): Promise<number> {
    const klines = await this.getByIndex<KlineData>(
      KlineStorage.STORE_NAME,
      'symbol_interval',
      [symbol, interval]
    );

    let deletedCount = 0;
    for (const kline of klines) {
      if (kline.timestamp < beforeTimestamp && kline.id) {
        await this.delete(KlineStorage.STORE_NAME, kline.id);
        deletedCount++;
      }
    }

    return deletedCount;
  }

  /**
   * 获取K线统计信息
   */
  async getKlineStats(symbol: string, interval: string): Promise<{
    count: number;
    oldestTimestamp?: number;
    newestTimestamp?: number;
  }> {
    const klines = await this.getByIndex<KlineData>(
      KlineStorage.STORE_NAME,
      'symbol_interval',
      [symbol, interval]
    );

    if (klines.length === 0) {
      return { count: 0 };
    }

    const timestamps = klines.map(k => k.timestamp).sort((a, b) => a - b);

    return {
      count: klines.length,
      oldestTimestamp: timestamps[0],
      newestTimestamp: timestamps[timestamps.length - 1],
    };
  }

  /**
   * K线数据去重
   */
  private deduplicateKlines(klines: Omit<KlineData, 'id' | 'createdAt'>[]): Omit<KlineData, 'id' | 'createdAt'>[] {
    const map = new Map<string, Omit<KlineData, 'id' | 'createdAt'>>();

    for (const kline of klines) {
      const key = `${kline.symbol}_${kline.interval}_${kline.timestamp}`;
      // 保留最新的数据（如果有重复）
      if (!map.has(key) || kline.closeTime > (map.get(key)?.closeTime || 0)) {
        map.set(key, kline);
      }
    }

    return Array.from(map.values());
  }

  /**
   * 将间隔字符串转换为毫秒
   */
  private intervalToMilliseconds(interval: string): number {
    const unit = interval.slice(-1);
    const value = parseInt(interval.slice(0, -1));

    switch (unit) {
      case 'm': return value * 60 * 1000;
      case 'h': return value * 60 * 60 * 1000;
      case 'd': return value * 24 * 60 * 60 * 1000;
      case 'w': return value * 7 * 24 * 60 * 60 * 1000;
      case 'M': return value * 30 * 24 * 60 * 60 * 1000; // 近似
      default: return 60 * 1000; // 默认1分钟
    }
  }

  /**
   * 确保数据库已初始化（继承自父类）
   */

}
