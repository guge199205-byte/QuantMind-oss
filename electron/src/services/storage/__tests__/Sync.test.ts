/**
 * 同步服务测试
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { SyncService, OfflineQueue, ConflictResolver } from '../index';

describe('SyncService', () => {
  let syncService: SyncService;

  beforeEach(() => {
    syncService = new SyncService();
  });

  it('应该能够注册存储', () => {
    const syncCallback = async () => {
      return { synced: 10 };
    };

    syncService.registerStore('klines', syncCallback);
    const state = syncService.getSyncState('klines');

    expect(state).toBeDefined();
    expect(state?.store).toBe('klines');
  });

  it('应该能够执行同步', async () => {
    let synced = false;

    syncService.registerStore('test', async () => {
      synced = true;
      return { success: true };
    });

    const results = await syncService.sync({ stores: ['test'], forceSync: true });

    expect(results).toHaveLength(1);
    expect(synced).toBe(true);
  });

  it('应该能够获取所有同步状态', () => {
    syncService.registerStore('store1', async () => ({}));
    syncService.registerStore('store2', async () => ({}));

    const states = syncService.getAllSyncStates();
    expect(states.length).toBeGreaterThanOrEqual(2);
  });
});

describe('OfflineQueue', () => {
  let queue: OfflineQueue;

  beforeEach(() => {
    queue = new OfflineQueue({ maxQueueSize: 10 });
    queue.clearQueue();
  });

  it('应该能够添加请求到队列', () => {
    queue.enqueue({
      method: 'POST',
      url: '/api/data',
      data: { test: true },
      priority: 1,
    });

    const status = queue.getStatus();
    expect(status.queueSize).toBe(1);
  });

  it('应该能够移除请求', () => {
    queue.enqueue({
      method: 'GET',
      url: '/api/test',
      priority: 1,
    });

    const status = queue.getStatus();
    const firstRequest = status.requests[0];

    const removed = queue.removeRequest(firstRequest.id);
    expect(removed).toBe(true);
    expect(queue.getStatus().queueSize).toBe(0);
  });

  it('应该能够清空队列', () => {
    queue.enqueue({ method: 'GET', url: '/api/1', priority: 1 });
    queue.enqueue({ method: 'GET', url: '/api/2', priority: 1 });

    queue.clearQueue();
    expect(queue.getStatus().queueSize).toBe(0);
  });
});

describe('ConflictResolver', () => {
  let resolver: ConflictResolver;

  beforeEach(() => {
    resolver = new ConflictResolver();
  });

  it('应该能够检测冲突', () => {
    const local = {
      id: 1,
      version: 1,
      timestamp: 1000,
      data: 'local',
    };

    const remote = {
      id: 1,
      version: 2,
      timestamp: 2000,
      data: 'remote',
    };

    const conflict = resolver.detectConflict(local, remote);
    expect(conflict).not.toBeNull();
    expect(conflict?.id).toBe('1');
  });

  it('应该能够使用远程数据解决冲突', () => {
    resolver.setDefaultStrategy('remote');

    const local = { id: 1, version: 1, data: 'local' };
    const remote = { id: 1, version: 2, data: 'remote' };
    const conflict = { id: '1', local, remote };

    const resolved = resolver.resolve(conflict);
    expect(resolved.data).toBe('remote');
  });

  it('应该能够使用本地数据解决冲突', () => {
    resolver.setDefaultStrategy('local');

    const local = { id: 1, version: 1, data: 'local' };
    const remote = { id: 1, version: 2, data: 'remote' };
    const conflict = { id: '1', local, remote };

    const resolved = resolver.resolve(conflict);
    expect(resolved.data).toBe('local');
  });

  it('应该能够批量解决冲突', () => {
    resolver.setDefaultStrategy('remote');

    const conflicts = [
      { id: '1', local: { id: 1, data: 'local1' }, remote: { id: 1, data: 'remote1' } },
      { id: '2', local: { id: 2, data: 'local2' }, remote: { id: 2, data: 'remote2' } },
    ];

    const resolved = resolver.resolveBatch(conflicts);
    expect(resolved).toHaveLength(2);
    expect(resolved[0].data).toBe('remote1');
    expect(resolved[1].data).toBe('remote2');
  });
});
