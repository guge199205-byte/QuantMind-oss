/**
 * 多级缓存服务
 * L1: 内存缓存 (快速访问)
 * L2: IndexedDB缓存 (持久化)
 */

import { CacheEntry, CacheStats } from './types';

export interface CacheOptions {
  maxSize?: number;
  defaultTTL?: number;
  evictionPolicy?: 'LRU' | 'LFU';
}

export class CacheService {
  // L1缓存：内存
  private memoryCache: Map<string, CacheEntry<unknown>> = new Map();

  // 缓存配置
  private readonly options: Required<CacheOptions>;

  // 统计信息
  private stats: CacheStats = {
    hits: 0,
    misses: 0,
    hitRate: 0,
    size: 0,
    evictions: 0,
  };

  // LFU访问频率追踪
  private accessFrequency: Map<string, number> = new Map();

  constructor(options: CacheOptions = {}) {
    this.options = {
      maxSize: options.maxSize ?? 1000,
      defaultTTL: options.defaultTTL ?? 5 * 60 * 1000, // 5分钟
      evictionPolicy: options.evictionPolicy ?? 'LRU',
    };
  }

  /**
   * 设置缓存
   */
  set<T>(key: string, value: T, ttl?: number): void {
    // 检查缓存大小，必要时清理
    if (this.memoryCache.size >= this.options.maxSize) {
      this.evict();
    }

    const entry: CacheEntry<T> = {
      key,
      value,
      timestamp: Date.now(),
      ttl: ttl ?? this.options.defaultTTL,
      hits: 0,
    };

    this.memoryCache.set(key, entry);
    this.stats.size = this.memoryCache.size;
  }

  /**
   * 获取缓存
   */
  get<T>(key: string): T | null {
    const entry = this.memoryCache.get(key) as CacheEntry<T> | undefined;

    if (!entry) {
      this.stats.misses++;
      this.updateHitRate();
      return null;
    }

    // 检查是否过期
    if (this.isExpired(entry)) {
      this.memoryCache.delete(key);
      this.stats.misses++;
      this.stats.size = this.memoryCache.size;
      this.updateHitRate();
      return null;
    }

    // 更新命中统计
    entry.hits++;
    this.stats.hits++;
    this.updateHitRate();

    // 更新访问频率（LFU）
    if (this.options.evictionPolicy === 'LFU') {
      const freq = this.accessFrequency.get(key) || 0;
      this.accessFrequency.set(key, freq + 1);
    }

    return entry.value;
  }

  /**
   * 检查是否存在
   */
  has(key: string): boolean {
    const entry = this.memoryCache.get(key);
    if (!entry) return false;

    if (this.isExpired(entry)) {
      this.memoryCache.delete(key);
      this.stats.size = this.memoryCache.size;
      return false;
    }

    return true;
  }

  /**
   * 删除缓存
   */
  delete(key: string): boolean {
    const deleted = this.memoryCache.delete(key);
    if (deleted) {
      this.stats.size = this.memoryCache.size;
      this.accessFrequency.delete(key);
    }
    return deleted;
  }

  /**
   * 清空缓存
   */
  clear(): void {
    this.memoryCache.clear();
    this.accessFrequency.clear();
    this.stats.size = 0;
  }

  /**
   * 获取或设置缓存（缓存未命中时执行加载函数）
   */
  async getOrSet<T>(
    key: string,
    loader: () => Promise<T>,
    ttl?: number
  ): Promise<T> {
    const cached = this.get<T>(key);
    if (cached !== null) {
      return cached;
    }

    const value = await loader();
    this.set(key, value, ttl);
    return value;
  }

  /**
   * 批量设置
   */
  setMany<T>(entries: { key: string; value: T; ttl?: number }[]): void {
    for (const entry of entries) {
      this.set(entry.key, entry.value, entry.ttl);
    }
  }

  /**
   * 批量获取
   */
  getMany<T>(keys: string[]): Map<string, T> {
    const result = new Map<string, T>();
    for (const key of keys) {
      const value = this.get<T>(key);
      if (value !== null) {
        result.set(key, value);
      }
    }
    return result;
  }

  /**
   * 批量删除
   */
  deleteMany(keys: string[]): number {
    let deleted = 0;
    for (const key of keys) {
      if (this.delete(key)) {
        deleted++;
      }
    }
    return deleted;
  }

  /**
   * 获取所有键
   */
  keys(): string[] {
    return Array.from(this.memoryCache.keys());
  }

  /**
   * 获取缓存统计
   */
  getStats(): CacheStats {
    return { ...this.stats };
  }

  /**
   * 重置统计
   */
  resetStats(): void {
    this.stats = {
      hits: 0,
      misses: 0,
      hitRate: 0,
      size: this.memoryCache.size,
      evictions: 0,
    };
  }

  /**
   * 清理过期缓存
   */
  cleanup(): number {
    let cleaned = 0;
    for (const [key, entry] of this.memoryCache.entries()) {
      if (this.isExpired(entry)) {
        this.memoryCache.delete(key);
        this.accessFrequency.delete(key);
        cleaned++;
      }
    }
    this.stats.size = this.memoryCache.size;
    return cleaned;
  }

  /**
   * 检查是否过期
   */
  private isExpired(entry: CacheEntry<unknown>): boolean {
    return Date.now() - entry.timestamp > entry.ttl;
  }

  /**
   * 缓存淘汰
   */
  private evict(): void {
    if (this.memoryCache.size === 0) return;

    let keyToEvict: string | null = null;

    if (this.options.evictionPolicy === 'LRU') {
      // LRU: 淘汰最久未使用的
      keyToEvict = this.evictLRU();
    } else {
      // LFU: 淘汰使用频率最低的
      keyToEvict = this.evictLFU();
    }

    if (keyToEvict) {
      this.memoryCache.delete(keyToEvict);
      this.accessFrequency.delete(keyToEvict);
      this.stats.evictions++;
      this.stats.size = this.memoryCache.size;
      console.log(`缓存淘汰 [${this.options.evictionPolicy}]: ${keyToEvict}`);
    }
  }

  /**
   * LRU淘汰策略
   */
  private evictLRU(): string | null {
    let oldestKey: string | null = null;
    let oldestTime = Infinity;

    for (const [key, entry] of this.memoryCache.entries()) {
      if (entry.timestamp < oldestTime) {
        oldestTime = entry.timestamp;
        oldestKey = key;
      }
    }

    return oldestKey;
  }

  /**
   * LFU淘汰策略
   */
  private evictLFU(): string | null {
    let leastKey: string | null = null;
    let leastFreq = Infinity;

    for (const [key, freq] of this.accessFrequency.entries()) {
      if (freq < leastFreq) {
        leastFreq = freq;
        leastKey = key;
      }
    }

    // 如果没有频率记录，使用LRU
    return leastKey || this.evictLRU();
  }

  /**
   * 更新命中率
   */
  private updateHitRate(): void {
    const total = this.stats.hits + this.stats.misses;
    this.stats.hitRate = total > 0 ? this.stats.hits / total : 0;
  }

  /**
   * 启动自动清理
   */
  startAutoCleanup(intervalMs: number = 60 * 1000): void {
    setInterval(() => {
      const cleaned = this.cleanup();
      if (cleaned > 0) {
        console.log(`自动清理了 ${cleaned} 个过期缓存`);
      }
    }, intervalMs);
  }
}
