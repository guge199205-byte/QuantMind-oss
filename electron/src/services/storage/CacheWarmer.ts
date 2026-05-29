/**
 * 缓存预热服务
 * 在应用启动或空闲时预加载常用数据
 */

import { CacheService } from './CacheService';

export interface WarmupTask {
  key: string;
  loader: () => Promise<unknown>;
  priority: 'high' | 'medium' | 'low';
  category?: string;
}

export interface WarmupOptions {
  onStartup?: boolean;
  onIdle?: boolean;
  idleDelay?: number;
  batchSize?: number;
}

export class CacheWarmer {
  private cache: CacheService;
  private tasks: WarmupTask[] = [];
  private isWarming: boolean = false;
  private options: Required<WarmupOptions>;

  constructor(cache: CacheService, options: WarmupOptions = {}) {
    this.cache = cache;
    this.options = {
      onStartup: options.onStartup ?? true,
      onIdle: options.onIdle ?? true,
      idleDelay: options.idleDelay ?? 2000,
      batchSize: options.batchSize ?? 5,
    };

    if (this.options.onStartup) {
      this.setupStartupWarming();
    }

    if (this.options.onIdle) {
      this.setupIdleWarming();
    }
  }

  /**
   * 注册预热任务
   */
  register(task: WarmupTask): void {
    this.tasks.push(task);
    console.log(`预热任务已注册: ${task.key}, 优先级: ${task.priority}`);
  }

  /**
   * 批量注册任务
   */
  registerMany(tasks: WarmupTask[]): void {
    tasks.forEach(task => this.register(task));
  }

  /**
   * 开始预热
   */
  async warmup(category?: string): Promise<void> {
    if (this.isWarming) {
      console.log('预热正在进行中，跳过');
      return;
    }

    this.isWarming = true;
    console.log('开始缓存预热...');

    try {
      // 筛选任务
      let tasksToWarm = category
        ? this.tasks.filter(t => t.category === category)
        : this.tasks;

      // 按优先级排序
      tasksToWarm = this.sortByPriority(tasksToWarm);

      // 分批处理
      await this.warmupBatch(tasksToWarm);

      console.log('缓存预热完成');
    } catch (error) {
      console.error('缓存预热失败:', error);
    } finally {
      this.isWarming = false;
    }
  }

  /**
   * 分批预热
   */
  private async warmupBatch(tasks: WarmupTask[]): Promise<void> {
    for (let i = 0; i < tasks.length; i += this.options.batchSize) {
      const batch = tasks.slice(i, i + this.options.batchSize);

      // 并行处理批次
      await Promise.allSettled(
        batch.map(task => this.warmupTask(task))
      );

      // 批次间稍作延迟，避免资源占用过高
      if (i + this.options.batchSize < tasks.length) {
        await this.sleep(100);
      }
    }
  }

  /**
   * 预热单个任务
   */
  private async warmupTask(task: WarmupTask): Promise<void> {
    try {
      // 检查是否已缓存
      if (this.cache.has(task.key)) {
        console.log(`跳过已缓存的任务: ${task.key}`);
        return;
      }

      console.log(`预热中: ${task.key}`);
      const value = await task.loader();
      this.cache.set(task.key, value);
      console.log(`预热成功: ${task.key}`);
    } catch (error) {
      console.error(`预热失败: ${task.key}`, error);
    }
  }

  /**
   * 按优先级排序
   */
  private sortByPriority(tasks: WarmupTask[]): WarmupTask[] {
    const priorityOrder = { high: 3, medium: 2, low: 1 };
    return tasks.sort((a, b) => priorityOrder[b.priority] - priorityOrder[a.priority]);
  }

  /**
   * 设置启动时预热
   */
  private setupStartupWarming(): void {
    // 在下一个事件循环执行，避免阻塞启动
    setTimeout(() => {
      console.log('执行启动预热');
      this.warmup();
    }, 0);
  }

  /**
   * 设置空闲时预热
   */
  private setupIdleWarming(): void {
    let idleTimer: NodeJS.Timeout | null = null;

    const resetIdleTimer = () => {
      if (idleTimer !== null) {
        clearTimeout(idleTimer);
      }

      idleTimer = window.setTimeout(() => {
        if (!this.isWarming) {
          console.log('检测到空闲，执行预热');
          this.warmup();
        }
      }, this.options.idleDelay) as unknown as NodeJS.Timeout;
    };

    // 监听用户活动
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach(event => {
      window.addEventListener(event, resetIdleTimer, { passive: true });
    });

    // 初始启动计时器
    resetIdleTimer();
  }

  /**
   * 预热常用数据
   */
  async warmupCommon(): Promise<void> {
    const commonTasks: WarmupTask[] = [
      {
        key: 'market:symbols',
        loader: async () => {
          // 加载交易对列表
          return [];
        },
        priority: 'high',
        category: 'market',
      },
      {
        key: 'user:preferences',
        loader: async () => {
          // 加载用户偏好
          return {};
        },
        priority: 'high',
        category: 'user',
      },
      {
        key: 'market:tickers',
        loader: async () => {
          // 加载行情数据
          return {};
        },
        priority: 'medium',
        category: 'market',
      },
    ];

    this.registerMany(commonTasks);
    await this.warmup();
  }

  /**
   * 获取状态
   */
  getStatus(): {
    totalTasks: number;
    isWarming: boolean;
    cachedTasks: number;
  } {
    const cachedTasks = this.tasks.filter(task => this.cache.has(task.key)).length;

    return {
      totalTasks: this.tasks.length,
      isWarming: this.isWarming,
      cachedTasks,
    };
  }

  /**
   * 清除所有任务
   */
  clearTasks(): void {
    this.tasks = [];
  }

  /**
   * 延迟函数
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
