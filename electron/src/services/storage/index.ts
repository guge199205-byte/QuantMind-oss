/**
 * 存储服务模块导出
 */

// 核心存储服务
export { StorageService } from './StorageService';
export { KlineStorage } from './KlineStorage';
export { TradeStorage } from './TradeStorage';
export { ConfigStorage } from './ConfigStorage';

// 同步服务
export { SyncService } from './SyncService';
export type { SyncOptions, SyncResult } from './SyncService';

// 离线队列
export { OfflineQueue } from './OfflineQueue';
export type { QueuedRequest, QueueOptions } from './OfflineQueue';

// 冲突解决
export { ConflictResolver, conflictStrategies } from './ConflictResolver';
export type { ConflictResolution, DataRecord, Conflict, ConflictResolutionStrategy } from './ConflictResolver';

// 缓存服务
export { CacheService } from './CacheService';
export type { CacheOptions } from './CacheService';

// 预加载策略
export { PreloadStrategy } from './PreloadStrategy';
export type { PreloadTask, PreloadOptions } from './PreloadStrategy';

// 缓存预热
export { CacheWarmer } from './CacheWarmer';
export type { WarmupTask, WarmupOptions } from './CacheWarmer';

// 类型定义
export type {
  DatabaseConfig,
  StoreConfig,
  IndexConfig,
  KlineData,
  TradeRecord,
  OrderRecord,
  StrategyConfig,
  UserConfig,
  QueryOptions,
  RangeQuery,
  BatchResult,
  SyncState,
  CacheEntry,
  CacheStats,
  StorageStats,
} from './types';
