/**
 * 存储服务使用示例
 */

import {
  KlineStorage,
  TradeStorage,
  ConfigStorage,
  SyncService,
  CacheService,
  CacheWarmer,
  PreloadStrategy,
  OfflineQueue,
  ConflictResolver,
} from './index';

/**
 * 示例1: K线数据存储
 */
async function exampleKlineStorage() {
  const klineStorage = new KlineStorage();
  await klineStorage.init();

  // 保存K线数据
  const kline = {
    symbol: 'BTCUSDT',
    interval: '1h',
    timestamp: Date.now(),
    open: 50000,
    high: 51000,
    low: 49000,
    close: 50500,
    volume: 100,
    closeTime: Date.now(),
    quoteVolume: 5000000,
    trades: 1000,
    takerBuyBaseVolume: 60,
    takerBuyQuoteVolume: 3000000,
  };

  const id = await klineStorage.saveKline(kline);
  console.log('K线已保存, ID:', id);

  // 获取最新K线
  const latestKlines = await klineStorage.getLatestKlines('BTCUSDT', '1h', 100);
  console.log('最新K线数量:', latestKlines.length);

  // 获取时间范围内的K线
  const rangeKlines = await klineStorage.getKlinesByTimeRange(
    'BTCUSDT',
    '1h',
    {
      start: Date.now() - 24 * 60 * 60 * 1000, // 24小时前
      end: Date.now(),
      limit: 1000,
    }
  );
  console.log('范围内K线数量:', rangeKlines.length);

  klineStorage.close();
}

/**
 * 示例2: 交易记录存储
 */
async function exampleTradeStorage() {
  const tradeStorage = new TradeStorage();
  await tradeStorage.init();

  // 保存交易记录
  const trade = {
    orderId: 'ORDER123456',
    symbol: 'BTCUSDT',
    side: 'BUY' as const,
    type: 'MARKET',
    price: 50000,
    quantity: 0.1,
    quoteQuantity: 5000,
    commission: 5,
    commissionAsset: 'USDT',
    timestamp: Date.now(),
    isMaker: false,
  };

  await tradeStorage.saveTrade(trade);

  // 保存订单记录
  const order = {
    orderId: 'ORDER123456',
    clientOrderId: 'CLIENT_ORDER_1',
    symbol: 'BTCUSDT',
    side: 'BUY' as const,
    type: 'MARKET',
    quantity: 0.1,
    status: 'FILLED',
    executedQty: 0.1,
    cummulativeQuoteQty: 5000,
    timestamp: Date.now(),
    updateTime: Date.now(),
  };

  await tradeStorage.saveOrder(order);

  // 获取交易统计
  const stats = await tradeStorage.getTradeStats('BTCUSDT');
  console.log('交易统计:', stats);

  tradeStorage.close();
}

/**
 * 示例3: 配置存储
 */
async function exampleConfigStorage() {
  const configStorage = new ConfigStorage();
  await configStorage.init();

  // 保存策略配置
  const strategy = {
    name: 'MA Cross Strategy',
    type: 'trend',
    symbol: 'BTCUSDT',
    interval: '1h',
    parameters: {
      fastPeriod: 10,
      slowPeriod: 20,
      stopLoss: 0.02,
      takeProfit: 0.05,
    },
    enabled: true,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };

  const strategyId = await configStorage.saveStrategy(strategy);
  console.log('策略已保存, ID:', strategyId);

  // 设置用户配置
  await configStorage.setConfig('theme', 'dark', 'ui', '界面主题');
  await configStorage.setConfig('language', 'zh-CN', 'ui', '界面语言');

  // 获取配置
  const theme = await configStorage.getConfig('theme');
  console.log('主题设置:', theme);

  // 导出配置（用于备份）
  const exported = await configStorage.exportConfig();
  console.log('配置已导出:', {
    strategies: exported.strategies.length,
    configs: exported.userConfig.length,
  });

  configStorage.close();
}

/**
 * 示例4: 数据同步
 */
async function exampleSyncService() {
  const syncService = new SyncService();
  const klineStorage = new KlineStorage();
  await klineStorage.init();

  // 注册同步回调
  syncService.registerStore('klines', async () => {
    console.log('正在同步K线数据...');
    // 实际的同步逻辑
    // 例如：从API获取最新数据并保存到IndexedDB
    return { synced: true };
  });

  // 执行同步
  const results = await syncService.sync({ forceSync: true });
  console.log('同步结果:', results);

  // 启动自动同步（每5分钟）
  syncService.startAutoSync(5 * 60 * 1000);
}

/**
 * 示例5: 缓存服务
 */
async function exampleCacheService() {
  // 创建缓存服务
  const cache = new CacheService({
    maxSize: 1000,
    defaultTTL: 5 * 60 * 1000, // 5分钟
    evictionPolicy: 'LRU',
  });

  // 设置缓存
  cache.set('market:BTCUSDT:ticker', {
    symbol: 'BTCUSDT',
    price: 50000,
    volume: 1000,
  });

  // 获取缓存
  const ticker = cache.get('market:BTCUSDT:ticker');
  console.log('缓存的行情:', ticker);

  // getOrSet模式
  const klines = await cache.getOrSet(
    'market:BTCUSDT:klines:1h',
    async () => {
      console.log('缓存未命中，加载数据...');
      // 从API或数据库加载
      return [];
    },
    10 * 60 * 1000 // 10分钟TTL
  );

  console.log('加载的K线条数:', (klines as Array<unknown>)?.length ?? 0);

  // 获取统计信息
  const stats = cache.getStats();
  console.log('缓存统计:', {
    命中率: `${(stats.hitRate * 100).toFixed(2)}%`,
    大小: stats.size,
    命中: stats.hits,
    未命中: stats.misses,
  });

  // 启动自动清理
  cache.startAutoCleanup(60 * 1000); // 每分钟清理过期缓存
}

/**
 * 示例6: 缓存预热
 */
async function exampleCacheWarmer() {
  const cache = new CacheService();

  // 创建预热服务
  const warmer = new CacheWarmer(cache, {
    onStartup: true,
    onIdle: true,
    idleDelay: 2000,
  });

  // 注册预热任务
  warmer.register({
    key: 'market:symbols',
    loader: async () => {
      console.log('预热交易对列表...');
      return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'];
    },
    priority: 'high',
    category: 'market',
  });

  warmer.register({
    key: 'user:preferences',
    loader: async () => {
      console.log('预热用户偏好...');
      return { theme: 'dark', language: 'zh-CN' };
    },
    priority: 'high',
    category: 'user',
  });

  // 执行预热
  await warmer.warmup();

  // 获取状态
  const status = warmer.getStatus();
  console.log('预热状态:', status);
}

/**
 * 示例7: 离线队列
 */
async function exampleOfflineQueue() {
  const queue = new OfflineQueue({
    maxRetries: 3,
    retryDelay: 1000,
    maxQueueSize: 100,
  });

  // 添加离线请求
  queue.enqueue({
    method: 'POST',
    url: '/api/orders',
    data: {
      symbol: 'BTCUSDT',
      side: 'BUY',
      quantity: 0.1,
    },
    priority: 10, // 高优先级
  });

  // 获取队列状态
  const status = queue.getStatus();
  console.log('队列状态:', {
    大小: status.queueSize,
    处理中: status.processing,
    在线: status.isOnline,
  });

  // 当网络恢复时，会自动处理队列
}

/**
 * 示例8: 冲突解决
 */
async function exampleConflictResolver() {
  const resolver = new ConflictResolver();

  // 设置默认策略
  resolver.setDefaultStrategy('remote');

  // 检测冲突
  const local = {
    id: 1,
    version: 1,
    timestamp: Date.now() - 1000,
    data: 'local data',
  };

  const remote = {
    id: 1,
    version: 2,
    timestamp: Date.now(),
    data: 'remote data',
  };

  const conflict = resolver.detectConflict(local, remote);

  if (conflict) {
    console.log('检测到冲突:', resolver.getConflictSummary(conflict));

    // 解决冲突
    const resolved = resolver.resolve(conflict);
    console.log('冲突已解决:', resolved);
  }
}

/**
 * 示例9: 预加载策略
 */
async function examplePreloadStrategy() {
  const preload = new PreloadStrategy({
    maxConcurrent: 3,
    timeout: 10000,
  });

  // 添加预加载任务
  preload.addTask({
    key: 'chart:BTCUSDT',
    loader: async () => {
      console.log('预加载BTC图表数据...');
      return { symbol: 'BTCUSDT', data: [] };
    },
    priority: 8,
    estimatedTime: 2000,
  });

  // 记录用户访问
  preload.recordAccess('page:market');
  preload.recordAccess('page:chart');

  // 预测下一步访问
  const predictions = preload.predictNext('page:market');
  console.log('预测下一步访问:', predictions);

  // 智能预加载
  const loaders = new Map([
    ['page:chart', async () => ({ data: 'chart' })],
    ['page:trade', async () => ({ data: 'trade' })],
  ]);

  await preload.smartPreload('page:market', loaders);
}

/**
 * 示例10: 完整集成示例
 */
async function exampleIntegration() {
  // 初始化所有服务
  const klineStorage = new KlineStorage();
  await klineStorage.init();

  const cache = new CacheService();
  const warmer = new CacheWarmer(cache);
  const syncService = new SyncService();
  const preload = new PreloadStrategy();
  console.log('preload status', preload.getStatus());

  // 注册同步
  syncService.registerStore('klines', async () => {
    const lastSync = syncService.getIncrementalTimestamp('klines');
    console.log('增量同步K线，从时间:', new Date(lastSync));
    // 同步逻辑...
    return { synced: true };
  });

  // 注册预热
  warmer.register({
    key: 'klines:BTCUSDT:1h',
    loader: async () => {
      return cache.getOrSet('klines:BTCUSDT:1h', async () => {
        return klineStorage.getLatestKlines('BTCUSDT', '1h', 100);
      });
    },
    priority: 'high',
  });

  // 启动服务
  await warmer.warmup();
  syncService.startAutoSync();
  cache.startAutoCleanup();

  console.log('所有服务已启动');
}

// 导出示例
export {
  exampleKlineStorage,
  exampleTradeStorage,
  exampleConfigStorage,
  exampleSyncService,
  exampleCacheService,
  exampleCacheWarmer,
  exampleOfflineQueue,
  exampleConflictResolver,
  examplePreloadStrategy,
  exampleIntegration,
};
