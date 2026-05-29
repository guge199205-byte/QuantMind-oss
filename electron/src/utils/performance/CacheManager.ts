/**
 * 缓存管理器
 * 实现LRU缓存策略
 */

export interface CacheOptions {
  maxSize?: number;
  ttl?: number; // 毫秒
  onEvict?: (key: string, value: any) => void;
}

interface CacheEntry<T> {
  value: T;
  timestamp: number;
  accessCount: number;
}

export class CacheManager<K = string, V = any> {
  private cache: Map<K, CacheEntry<V>> = new Map();
  private accessOrder: K[] = [];
  private maxSize: number;
  private ttl: number;
  private onEvict?: (key: K, value: V) => void;

  constructor(options: CacheOptions = {}) {
    this.maxSize = options.maxSize || 100;
    this.ttl = options.ttl || 5 * 60 * 1000; // 默认5分钟
    this.onEvict = options.onEvict as any;
  }

  /**
   * 设置缓存
   */
  set(key: K, value: V): void {
    // 检查是否已存在
    if (this.cache.has(key)) {
      this.updateAccessOrder(key);
    } else {
      // 检查容量
      if (this.cache.size >= this.maxSize) {
        this.evictLRU();
      }
      this.accessOrder.push(key);
    }

    // 设置缓存项
    this.cache.set(key, {
      value,
      timestamp: Date.now(),
      accessCount: 0
    });
  }

  /**
   * 获取缓存
   */
  get(key: K): V | undefined {
    const entry = this.cache.get(key);

    if (!entry) {
      return undefined;
    }

    // 检查是否过期
    if (this.isExpired(entry)) {
      this.delete(key);
      return undefined;
    }

    // 更新访问信息
    entry.accessCount++;
    this.updateAccessOrder(key);

    return entry.value;
  }

  /**
   * 检查是否存在
   */
  has(key: K): boolean {
    const entry = this.cache.get(key);
    if (!entry) return false;

    if (this.isExpired(entry)) {
      this.delete(key);
      return false;
    }

    return true;
  }

  /**
   * 删除缓存
   */
  delete(key: K): boolean {
    const entry = this.cache.get(key);
    if (!entry) return false;

    if (this.onEvict) {
      this.onEvict(key, entry.value);
    }

    this.cache.delete(key);
    this.accessOrder = this.accessOrder.filter(k => k !== key);

    return true;
  }

  /**
   * 清空缓存
   */
  clear(): void {
    if (this.onEvict) {
      this.cache.forEach((entry, key) => {
        this.onEvict!(key, entry.value);
      });
    }

    this.cache.clear();
    this.accessOrder = [];
  }

  /**
   * 获取缓存大小
   */
  size(): number {
    return this.cache.size;
  }

  /**
   * 获取所有键
   */
  keys(): K[] {
    return Array.from(this.cache.keys());
  }

  /**
   * 获取所有值
   */
  values(): V[] {
    return Array.from(this.cache.values()).map(entry => entry.value);
  }

  /**
   * 获取缓存统计
   */
  getStats(): {
    size: number;
    maxSize: number;
    hitRate: number;
    avgAccessCount: number;
  } {
    const entries = Array.from(this.cache.values());
    const totalAccess = entries.reduce((sum, e) => sum + e.accessCount, 0);
    const avgAccessCount = entries.length > 0 ? totalAccess / entries.length : 0;

    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      hitRate: 0, // 需要额外跟踪未命中次数
      avgAccessCount
    };
  }

  /**
   * 清理过期缓存
   */
  cleanup(): number {
    let removed = 0;
    const now = Date.now();

    this.cache.forEach((entry, key) => {
      if (now - entry.timestamp > this.ttl) {
        this.delete(key);
        removed++;
      }
    });

    return removed;
  }

  /**
   * 更新访问顺序
   */
  private updateAccessOrder(key: K): void {
    const index = this.accessOrder.indexOf(key);
    if (index > -1) {
      this.accessOrder.splice(index, 1);
    }
    this.accessOrder.push(key);
  }

  /**
   * 淘汰最近最少使用的项
   */
  private evictLRU(): void {
    if (this.accessOrder.length === 0) return;

    const lruKey = this.accessOrder[0];
    this.delete(lruKey);
  }

  /**
   * 检查是否过期
   */
  private isExpired(entry: CacheEntry<V>): boolean {
    return Date.now() - entry.timestamp > this.ttl;
  }

  /**
   * 设置TTL
   */
  setTTL(ttl: number): void {
    this.ttl = ttl;
  }

  /**
   * 设置最大容量
   */
  setMaxSize(maxSize: number): void {
    this.maxSize = maxSize;

    // 如果当前大小超过新的最大容量，淘汰多余的项
    while (this.cache.size > this.maxSize) {
      this.evictLRU();
    }
  }
}

// 全局缓存实例
export const globalCache = new CacheManager({
  maxSize: 1000,
  ttl: 10 * 60 * 1000 // 10分钟
});

// API响应缓存
export const apiCache = new CacheManager({
  maxSize: 500,
  ttl: 5 * 60 * 1000 // 5分钟
});

// 图表数据缓存
export const chartCache = new CacheManager({
  maxSize: 100,
  ttl: 30 * 1000 // 30秒
});
