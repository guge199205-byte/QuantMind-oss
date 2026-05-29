/**
 * 数据同步服务
 */

import { SyncState } from './types';

export interface SyncOptions {
  incrementalOnly?: boolean;
  forceSync?: boolean;
  stores?: string[];
}

export interface SyncResult {
  store: string;
  synced: number;
  errors: number;
  duration: number;
}

export class SyncService {
  private syncStates: Map<string, SyncState> = new Map();
  private syncCallbacks: Map<string, () => Promise<unknown>> = new Map();
  private isOnline: boolean = navigator.onLine;

  constructor() {
    this.setupOnlineListener();
    this.loadSyncStates();
  }

  /**
   * 注册同步回调
   */
  registerStore(store: string, syncCallback: () => Promise<unknown>): void {
    this.syncCallbacks.set(store, syncCallback);

    // 初始化同步状态
    if (!this.syncStates.has(store)) {
      this.syncStates.set(store, {
        store,
        lastSyncTime: 0,
        version: 1,
        status: 'idle',
      });
    }
  }

  /**
   * 执行同步
   */
  async sync(options: SyncOptions = {}): Promise<SyncResult[]> {
    const storesToSync = options.stores || Array.from(this.syncCallbacks.keys());
    const results: SyncResult[] = [];

    for (const store of storesToSync) {
      const result = await this.syncStore(store, options);
      results.push(result);
    }

    return results;
  }

  /**
   * 同步单个存储
   */
  private async syncStore(store: string, options: SyncOptions): Promise<SyncResult> {
    const startTime = Date.now();
    const state = this.syncStates.get(store);

    if (!state) {
      return {
        store,
        synced: 0,
        errors: 1,
        duration: Date.now() - startTime,
      };
    }

    // 检查是否需要同步
    if (!this.shouldSync(state, options)) {
      return {
        store,
        synced: 0,
        errors: 0,
        duration: Date.now() - startTime,
      };
    }

    // 更新状态
    state.status = 'syncing';
    this.syncStates.set(store, state);

    try {
      const callback = this.syncCallbacks.get(store);
      if (callback) {
        await callback();
      }

      // 同步成功
      state.status = 'idle';
      state.lastSyncTime = Date.now();
      state.version++;
      this.syncStates.set(store, state);
      this.saveSyncStates();

      return {
        store,
        synced: 1,
        errors: 0,
        duration: Date.now() - startTime,
      };
    } catch (error) {
      // 同步失败
      state.status = 'error';
      state.error = (error as Error).message;
      this.syncStates.set(store, state);

      console.error(`同步失败 [${store}]:`, error);

      return {
        store,
        synced: 0,
        errors: 1,
        duration: Date.now() - startTime,
      };
    }
  }

  /**
   * 判断是否需要同步
   */
  private shouldSync(state: SyncState, options: SyncOptions): boolean {
    // 强制同步
    if (options.forceSync) {
      return true;
    }

    // 正在同步中
    if (state.status === 'syncing') {
      return false;
    }

    // 离线状态
    if (!this.isOnline && !options.incrementalOnly) {
      return false;
    }

    return true;
  }

  /**
   * 获取同步状态
   */
  getSyncState(store: string): SyncState | undefined {
    return this.syncStates.get(store);
  }

  /**
   * 获取所有同步状态
   */
  getAllSyncStates(): SyncState[] {
    return Array.from(this.syncStates.values());
  }

  /**
   * 重置同步状态
   */
  resetSyncState(store: string): void {
    const state = this.syncStates.get(store);
    if (state) {
      state.lastSyncTime = 0;
      state.version = 1;
      state.status = 'idle';
      state.error = undefined;
      this.syncStates.set(store, state);
      this.saveSyncStates();
    }
  }

  /**
   * 检查是否在线
   */
  isOnlineStatus(): boolean {
    return this.isOnline;
  }

  /**
   * 设置在线监听
   */
  private setupOnlineListener(): void {
    window.addEventListener('online', () => {
      this.isOnline = true;
      console.log('网络连接已恢复，触发自动同步');
      this.sync({ incrementalOnly: true });
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
      console.log('网络连接已断开，进入离线模式');
    });
  }

  /**
   * 保存同步状态到localStorage
   */
  private saveSyncStates(): void {
    try {
      const statesArray = Array.from(this.syncStates.entries());
      localStorage.setItem('sync_states', JSON.stringify(statesArray));
    } catch (error: unknown) {
      console.error('保存同步状态失败:', (error as Error).message ?? error);
    }
  }

  /**
   * 从localStorage加载同步状态
   */
  private loadSyncStates(): void {
    try {
      const saved = localStorage.getItem('sync_states');
      if (saved) {
        const statesArray = JSON.parse(saved) as [string, SyncState][];
        this.syncStates = new Map(statesArray);
      }
    } catch (error: unknown) {
      console.error('加载同步状态失败:', (error as Error).message ?? error);
    }
  }

  /**
   * 获取增量数据时间戳
   */
  getIncrementalTimestamp(store: string): number {
    const state = this.syncStates.get(store);
    return state?.lastSyncTime || 0;
  }

  /**
   * 启动自动同步
   */
  startAutoSync(intervalMs: number = 5 * 60 * 1000): void {
    setInterval(() => {
      if (this.isOnline) {
        this.sync({ incrementalOnly: true });
      }
    }, intervalMs);
  }
}
