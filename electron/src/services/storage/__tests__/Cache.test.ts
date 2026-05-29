/**
 * 缓存服务测试
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { CacheService, PreloadStrategy, CacheWarmer } from '../index';

describe('CacheService', () => {
  let cache: CacheService;

  beforeEach(() => {
    cache = new CacheService({
      maxSize: 10,
      defaultTTL: 1000,
      evictionPolicy: 'LRU',
    });
  });

  it('应该能够设置和获取缓存', () => {
    cache.set('key1', 'value1');
    const value = cache.get('key1');
    expect(value).toBe('value1');
  });

  it('应该能够处理缓存过期', async () => {
    cache.set('key2', 'value2', 100);

    // 等待过期
    await new Promise(resolve => setTimeout(resolve, 150));

    const value = cache.get('key2');
    expect(value).toBeNull();
  });

  it('应该能够检查缓存是否存在', () => {
    cache.set('key3', 'value3');
    expect(cache.has('key3')).toBe(true);
    expect(cache.has('nonexistent')).toBe(false);
  });

  it('应该能够删除缓存', () => {
    cache.set('key4', 'value4');
    const deleted = cache.delete('key4');

    expect(deleted).toBe(true);
    expect(cache.has('key4')).toBe(false);
  });

  it('应该能够清空缓存', () => {
    cache.set('key5', 'value5');
    cache.set('key6', 'value6');

    cache.clear();

    expect(cache.has('key5')).toBe(false);
    expect(cache.has('key6')).toBe(false);
  });

  it('应该能够批量操作', () => {
    cache.setMany([
      { key: 'k1', value: 'v1' },
      { key: 'k2', value: 'v2' },
      { key: 'k3', value: 'v3' },
    ]);

    const values = cache.getMany(['k1', 'k2', 'k3']);
    expect(values.size).toBe(3);
    expect(values.get('k1')).toBe('v1');
  });

  it('应该能够获取统计信息', () => {
    cache.set('stat1', 'value1');
    cache.get('stat1'); // 命中
    cache.get('nonexistent'); // 未命中

    const stats = cache.getStats();
    expect(stats.hits).toBe(1);
    expect(stats.misses).toBe(1);
    expect(stats.size).toBe(1);
  });

  it('应该能够触发LRU淘汰', () => {
    // 设置maxSize为3的缓存
    const smallCache = new CacheService({ maxSize: 3, evictionPolicy: 'LRU' });

    smallCache.set('a', '1');
    smallCache.set('b', '2');
    smallCache.set('c', '3');
    smallCache.set('d', '4'); // 应该淘汰'a'

    expect(smallCache.has('a')).toBe(false);
    expect(smallCache.has('d')).toBe(true);
  });

  it('应该能够getOrSet', async () => {
    let loaderCalled = false;

    const loader = async () => {
      loaderCalled = true;
      return 'loaded value';
    };

    const value1 = await cache.getOrSet('lazy1', loader);
    expect(value1).toBe('loaded value');
    expect(loaderCalled).toBe(true);

    loaderCalled = false;
    const value2 = await cache.getOrSet('lazy1', loader);
    expect(value2).toBe('loaded value');
    expect(loaderCalled).toBe(false); // 缓存命中，不应调用loader
  });
});

describe('PreloadStrategy', () => {
  let preload: PreloadStrategy;

  beforeEach(() => {
    preload = new PreloadStrategy({ maxConcurrent: 2 });
  });

  it('应该能够添加预加载任务', () => {
    const taskId = preload.addTask({
      key: 'task1',
      loader: async () => 'data',
      priority: 5,
      estimatedTime: 1000,
    });

    expect(taskId).toBeDefined();
  });

  it('应该能够处理预加载队列', async () => {
    let loaded = false;

    preload.addTask({
      key: 'task2',
      loader: async () => {
        loaded = true;
        return 'data';
      },
      priority: 5,
      estimatedTime: 100,
    });

    await preload.process();

    // 等待异步任务完成
    await new Promise(resolve => setTimeout(resolve, 200));

    expect(loaded).toBe(true);
  });

  it('应该能够记录访问历史', () => {
    preload.recordAccess('page1');
    preload.recordAccess('page2');
    preload.recordAccess('page3');

    const predictions = preload.predictNext('page1');
    expect(Array.isArray(predictions)).toBe(true);
  });

  it('应该能够获取状态', () => {
    preload.addTask({
      key: 'task3',
      loader: async () => 'data',
      priority: 5,
      estimatedTime: 1000,
    });

    const status = preload.getStatus();
    expect(status.queueSize).toBeGreaterThan(0);
  });
});

describe('CacheWarmer', () => {
  let cache: CacheService;
  let warmer: CacheWarmer;

  beforeEach(() => {
    cache = new CacheService();
    warmer = new CacheWarmer(cache, {
      onStartup: false,
      onIdle: false,
    });
  });

  it('应该能够注册预热任务', () => {
    warmer.register({
      key: 'warm1',
      loader: async () => 'data',
      priority: 'high',
    });

    const status = warmer.getStatus();
    expect(status.totalTasks).toBe(1);
  });

  it('应该能够执行预热', async () => {
    let warmed = false;

    warmer.register({
      key: 'warm2',
      loader: async () => {
        warmed = true;
        return 'data';
      },
      priority: 'high',
    });

    await warmer.warmup();

    expect(warmed).toBe(true);
    expect(cache.has('warm2')).toBe(true);
  });

  it('应该能够批量注册任务', () => {
    const tasks = [
      { key: 'w1', loader: async () => 'd1', priority: 'high' as const },
      { key: 'w2', loader: async () => 'd2', priority: 'medium' as const },
    ];

    warmer.registerMany(tasks);

    const status = warmer.getStatus();
    expect(status.totalTasks).toBe(2);
  });

  it('应该能够获取预热状态', () => {
    warmer.register({
      key: 'status1',
      loader: async () => 'data',
      priority: 'low',
    });

    const status = warmer.getStatus();
    expect(status).toHaveProperty('totalTasks');
    expect(status).toHaveProperty('isWarming');
    expect(status).toHaveProperty('cachedTasks');
  });
});
