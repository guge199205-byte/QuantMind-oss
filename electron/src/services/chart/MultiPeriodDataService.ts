/**
 * 多周期数据管理服务
 * 支持同时加载和管理多个时间周期的数据
 */

export interface Period {
  id: string;
  name: string;
  interval: string; // '1m', '5m', '15m', '1h', '1d' 等
  color: string;
  enabled: boolean;
}

export interface OHLCV {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MultiPeriodData {
  periods: Period[];
  data: Map<string, OHLCV[]>;
  alignedTimestamps: number[];
  currentPeriod: string;
}

export interface DataLoadOptions {
  symbol: string;
  startTime?: number;
  endTime?: number;
  limit?: number;
}

/**
 * 多周期数据服务类
 */
export class MultiPeriodDataService {
  private cache: Map<string, Map<string, OHLCV[]>>;
  private dataLoader: (symbol: string, interval: string, options: DataLoadOptions) => Promise<OHLCV[]>;

  constructor(dataLoader: (symbol: string, interval: string, options: DataLoadOptions) => Promise<OHLCV[]>) {
    this.cache = new Map();
    this.dataLoader = dataLoader;
  }

  /**
   * 加载多个周期的数据
   * @param symbol 交易对符号
   * @param periods 周期配置数组
   * @param options 加载选项
   * @returns 多周期数据
   */
  async loadPeriods(
    symbol: string,
    periods: Period[],
    options: DataLoadOptions = { symbol }
  ): Promise<MultiPeriodData> {
    const dataMap = new Map<string, OHLCV[]>();

    // 并发加载所有周期的数据
    const loadPromises = periods
      .filter(p => p.enabled)
      .map(async (period) => {
        const cacheKey = this.getCacheKey(symbol, period.interval);

        // 检查缓存
        if (this.cache.has(cacheKey)) {
          const cachedData = this.cache.get(cacheKey)!.get(period.id);
          if (cachedData && this.isCacheValid(cachedData, options)) {
            dataMap.set(period.id, cachedData);
            return;
          }
        }

        // 加载新数据
        try {
          const data = await this.dataLoader(symbol, period.interval, options);
          dataMap.set(period.id, data);

          // 更新缓存
          if (!this.cache.has(cacheKey)) {
            this.cache.set(cacheKey, new Map());
          }
          this.cache.get(cacheKey)!.set(period.id, data);
        } catch (error) {
          console.error(`加载周期 ${period.interval} 数据失败:`, error);
          dataMap.set(period.id, []);
        }
      });

    await Promise.all(loadPromises);

    // 对齐时间戳
    const alignedTimestamps = this.alignTimestamps(dataMap);

    return {
      periods: periods.filter(p => p.enabled),
      data: dataMap,
      alignedTimestamps,
      currentPeriod: periods[0]?.id || ''
    };
  }

  /**
   * 获取特定周期的数据
   * @param multiPeriodData 多周期数据
   * @param periodId 周期ID
   * @returns OHLCV数组
   */
  getPeriodData(multiPeriodData: MultiPeriodData, periodId: string): OHLCV[] {
    return multiPeriodData.data.get(periodId) || [];
  }

  /**
   * 切换当前周期
   * @param multiPeriodData 多周期数据
   * @param periodId 新的周期ID
   * @returns 更新后的多周期数据
   */
  switchPeriod(multiPeriodData: MultiPeriodData, periodId: string): MultiPeriodData {
    if (!multiPeriodData.data.has(periodId)) {
      throw new Error(`周期 ${periodId} 不存在`);
    }

    return {
      ...multiPeriodData,
      currentPeriod: periodId
    };
  }

  /**
   * 对齐多个周期的时间戳
   * @param dataMap 数据映射
   * @returns 对齐后的时间戳数组
   */
  private alignTimestamps(dataMap: Map<string, OHLCV[]>): number[] {
    if (dataMap.size === 0) return [];

    // 获取所有时间戳
    const allTimestamps = new Set<number>();

    for (const data of dataMap.values()) {
      data.forEach(item => allTimestamps.add(item.timestamp));
    }

    // 排序并返回
    return Array.from(allTimestamps).sort((a, b) => a - b);
  }

  /**
   * 同步数据到对齐的时间戳
   * @param data 原始数据
   * @param alignedTimestamps 对齐的时间戳
   * @returns 同步后的数据
   */
  syncDataToTimestamps(data: OHLCV[], alignedTimestamps: number[]): OHLCV[] {
    const syncedData: OHLCV[] = [];
    const dataMap = new Map(data.map(d => [d.timestamp, d]));

    let lastValidData: OHLCV | null = null;

    for (const timestamp of alignedTimestamps) {
      if (dataMap.has(timestamp)) {
        const item = dataMap.get(timestamp)!;
        syncedData.push(item);
        lastValidData = item;
      } else if (lastValidData) {
        // 使用前一个有效数据填充
        syncedData.push({
          ...lastValidData,
          timestamp,
          volume: 0
        });
      }
    }

    return syncedData;
  }

  /**
   * 获取缓存键
   * @param symbol 交易对符号
   * @param interval 时间间隔
   * @returns 缓存键
   */
  private getCacheKey(symbol: string, interval: string): string {
    return `${symbol}_${interval}`;
  }

  /**
   * 检查缓存是否有效
   * @param cachedData 缓存的数据
   * @param options 加载选项
   * @returns 是否有效
   */
  private isCacheValid(cachedData: OHLCV[], options: DataLoadOptions): boolean {
    if (cachedData.length === 0) return false;

    // 检查时间范围
    if (options.startTime || options.endTime) {
      const firstTimestamp = cachedData[0].timestamp;
      const lastTimestamp = cachedData[cachedData.length - 1].timestamp;

      if (options.startTime && firstTimestamp > options.startTime) return false;
      if (options.endTime && lastTimestamp < options.endTime) return false;
    }

    // 缓存有效期（5分钟）
    const now = Date.now();
    const lastTimestamp = cachedData[cachedData.length - 1].timestamp;
    const cacheAge = now - lastTimestamp;

    return cacheAge < 5 * 60 * 1000;
  }

  /**
   * 清除缓存
   * @param symbol 可选的交易对符号，不提供则清除所有
   */
  clearCache(symbol?: string): void {
    if (symbol) {
      // 清除特定交易对的缓存
      const keysToDelete: string[] = [];
      for (const key of this.cache.keys()) {
        if (key.startsWith(symbol + '_')) {
          keysToDelete.push(key);
        }
      }
      keysToDelete.forEach(key => this.cache.delete(key));
    } else {
      // 清除所有缓存
      this.cache.clear();
    }
  }

  /**
   * 获取缓存统计信息
   * @returns 缓存统计
   */
  getCacheStats(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys())
    };
  }

  /**
   * 合并多个周期的数据用于对比显示
   * @param multiPeriodData 多周期数据
   * @param periodIds 要对比的周期ID数组
   * @returns 合并后的数据映射
   */
  mergePeriodsForComparison(
    multiPeriodData: MultiPeriodData,
    periodIds: string[]
  ): Map<string, OHLCV[]> {
    const mergedData = new Map<string, OHLCV[]>();

    periodIds.forEach(periodId => {
      const data = this.getPeriodData(multiPeriodData, periodId);
      if (data.length > 0) {
        // 同步到对齐的时间戳
        const syncedData = this.syncDataToTimestamps(data, multiPeriodData.alignedTimestamps);
        mergedData.set(periodId, syncedData);
      }
    });

    return mergedData;
  }

  /**
   * 计算周期间的相关性
   * @param data1 周期1的数据
   * @param data2 周期2的数据
   * @returns 相关系数 (-1 到 1)
   */
  calculateCorrelation(data1: OHLCV[], data2: OHLCV[]): number {
    if (data1.length !== data2.length || data1.length === 0) {
      return 0;
    }

    const closes1 = data1.map(d => d.close);
    const closes2 = data2.map(d => d.close);

    const mean1 = closes1.reduce((a, b) => a + b, 0) / closes1.length;
    const mean2 = closes2.reduce((a, b) => a + b, 0) / closes2.length;

    let numerator = 0;
    let sumSq1 = 0;
    let sumSq2 = 0;

    for (let i = 0; i < closes1.length; i++) {
      const diff1 = closes1[i] - mean1;
      const diff2 = closes2[i] - mean2;
      numerator += diff1 * diff2;
      sumSq1 += diff1 * diff1;
      sumSq2 += diff2 * diff2;
    }

    const denominator = Math.sqrt(sumSq1 * sumSq2);
    return denominator === 0 ? 0 : numerator / denominator;
  }
}

/**
 * 预定义的周期配置
 */
export const PREDEFINED_PERIODS: Period[] = [
  { id: '1m', name: '1分钟', interval: '1m', color: '#3b82f6', enabled: false },
  { id: '5m', name: '5分钟', interval: '5m', color: '#8b5cf6', enabled: false },
  { id: '15m', name: '15分钟', interval: '15m', color: '#ec4899', enabled: false },
  { id: '30m', name: '30分钟', interval: '30m', color: '#f59e0b', enabled: false },
  { id: '1h', name: '1小时', interval: '1h', color: '#10b981', enabled: true },
  { id: '4h', name: '4小时', interval: '4h', color: '#06b6d4', enabled: false },
  { id: '1d', name: '1天', interval: '1d', color: '#6366f1', enabled: false },
  { id: '1w', name: '1周', interval: '1w', color: '#8b5cf6', enabled: false }
];

export default MultiPeriodDataService;
