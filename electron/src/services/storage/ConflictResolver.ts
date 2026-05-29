/**
 * 冲突解决服务
 * 处理本地和远程数据不一致的情况
 */

export type ConflictResolution = 'local' | 'remote' | 'merge' | 'manual';

export interface DataRecord {
  id?: string | number;
  version?: number;
  timestamp?: number;
  updatedAt?: number;
  [key: string]: unknown;
}

export interface Conflict<T extends DataRecord> {
  id: string;
  local: T;
  remote: T;
  field?: string;
}

export interface ConflictResolutionStrategy {
  strategy: ConflictResolution;
  resolver?: (local: unknown, remote: unknown) => unknown;
}

export class ConflictResolver {
  private strategies: Map<string, ConflictResolutionStrategy> = new Map();
  private defaultStrategy: ConflictResolution = 'remote'; // 默认使用远程数据

  /**
   * 设置默认策略
   */
  setDefaultStrategy(strategy: ConflictResolution): void {
    this.defaultStrategy = strategy;
  }

  /**
   * 为特定类型设置策略
   */
  setStrategy(type: string, strategy: ConflictResolutionStrategy): void {
    this.strategies.set(type, strategy);
  }

  /**
   * 检测冲突
   */
  detectConflict<T extends DataRecord>(local: T, remote: T): Conflict<T> | null {
    // 如果版本号不同，存在冲突
    if (local.version !== undefined && remote.version !== undefined) {
      if (local.version !== remote.version) {
        return { id: String(local.id), local, remote };
      }
    }

    // 如果时间戳不同，检查是否有实质性差异
    if (local.timestamp !== undefined && remote.timestamp !== undefined) {
      if (local.timestamp !== remote.timestamp) {
        // 检查数据内容是否不同
        if (!this.areRecordsEqual(local, remote)) {
          return { id: String(local.id), local, remote };
        }
      }
    }

    return null;
  }

  /**
   * 解决冲突
   */
  resolve<T extends DataRecord>(
    conflict: Conflict<T>,
    type?: string
  ): T {
    const strategy = this.strategies.get(type || 'default')?.strategy || this.defaultStrategy;

    switch (strategy) {
      case 'local':
        return this.useLocal(conflict);

      case 'remote':
        return this.useRemote(conflict);

      case 'merge':
        return this.merge(conflict, type);

      case 'manual':
        // 需要手动处理
        throw new Error('需要手动解决冲突');

      default:
        return this.useRemote(conflict);
    }
  }

  /**
   * 使用本地数据
   */
  private useLocal<T extends DataRecord>(conflict: Conflict<T>): T {
    console.log(`使用本地数据解决冲突: ${conflict.id}`);
    return conflict.local;
  }

  /**
   * 使用远程数据
   */
  private useRemote<T extends DataRecord>(conflict: Conflict<T>): T {
    console.log(`使用远程数据解决冲突: ${conflict.id}`);
    return conflict.remote;
  }

  /**
   * 合并数据
   */
  private merge<T extends DataRecord>(conflict: Conflict<T>, type?: string): T {
    console.log(`合并数据解决冲突: ${conflict.id}`);

    const customResolver = this.strategies.get(type || 'default')?.resolver;
    if (customResolver) {
      return customResolver(conflict.local, conflict.remote) as T;
    }

    // 默认合并策略：使用时间戳较新的字段
    return this.mergeByTimestamp(conflict.local, conflict.remote);
  }

  /**
   * 按时间戳合并
   */
  private mergeByTimestamp<T extends DataRecord>(local: T, remote: T): T {
    const localTime = local.updatedAt || local.timestamp || 0;
    const remoteTime = remote.updatedAt || remote.timestamp || 0;

    // 基于时间选择
    if (localTime > remoteTime) {
      return { ...remote, ...local };
    } else {
      return { ...local, ...remote };
    }
  }

  /**
   * 比较两个记录是否相等
   */
  private areRecordsEqual<T extends DataRecord>(local: T, remote: T): boolean {
    // 排除特定字段
    const excludeFields = ['id', 'version', 'timestamp', 'updatedAt', 'createdAt'];

    const localKeys = Object.keys(local).filter(k => !excludeFields.includes(k));
    const remoteKeys = Object.keys(remote).filter(k => !excludeFields.includes(k));

    if (localKeys.length !== remoteKeys.length) {
      return false;
    }

    for (const key of localKeys) {
      if (!this.isEqual(local[key], remote[key])) {
        return false;
      }
    }

    return true;
  }

  /**
   * 深度比较值
   */
  private isEqual(a: unknown, b: unknown): boolean {
    if (a === b) return true;
    if (a == null || b == null) return false;
    if (typeof a !== typeof b) return false;

    if (typeof a === 'object' && typeof b === 'object') {
      const keysA = Object.keys(a as Record<string, unknown>);
      const keysB = Object.keys(b as Record<string, unknown>);

      if (keysA.length !== keysB.length) return false;

      for (const key of keysA) {
        if (!this.isEqual((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key])) {
          return false;
        }
      }

      return true;
    }

    return false;
  }

  /**
   * 批量解决冲突
   */
  resolveBatch<T extends DataRecord>(
    conflicts: Conflict<T>[],
    type?: string
  ): T[] {
    return conflicts.map(conflict => this.resolve(conflict, type));
  }

  /**
   * 获取冲突摘要
   */
  getConflictSummary<T extends DataRecord>(conflict: Conflict<T>): string {
    const localTime = conflict.local.updatedAt || conflict.local.timestamp || 0;
    const remoteTime = conflict.remote.updatedAt || conflict.remote.timestamp || 0;

    return `冲突 [${conflict.id}]: 本地时间=${new Date(localTime).toISOString()}, 远程时间=${new Date(remoteTime).toISOString()}`;
  }
}

/**
 * 预定义的冲突解决策略
 */
export const conflictStrategies = {
  // 总是使用本地数据
  alwaysLocal: (): ConflictResolutionStrategy => ({
    strategy: 'local',
  }),

  // 总是使用远程数据
  alwaysRemote: (): ConflictResolutionStrategy => ({
    strategy: 'remote',
  }),

  // 按时间戳合并
  mergeByTime: (): ConflictResolutionStrategy => ({
    strategy: 'merge',
  }),

  // 自定义合并
  custom: (resolver: (local: unknown, remote: unknown) => unknown): ConflictResolutionStrategy => ({
    strategy: 'merge',
    resolver,
  }),
};
