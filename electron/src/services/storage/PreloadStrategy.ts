/**
 * 预加载策略服务
 * 智能预测和预加载用户可能需要的数据
 */

export interface PreloadTask {
  id: string;
  key: string;
  loader: () => Promise<unknown>;
  priority: number;
  estimatedTime: number;
  dependencies?: string[];
}

export interface PreloadOptions {
  maxConcurrent?: number;
  timeout?: number;
  retryOnError?: boolean;
}

export class PreloadStrategy {
  private queue: PreloadTask[] = [];
  private processing: Set<string> = new Set();
  private completed: Set<string> = new Set();
  private failed: Set<string> = new Set();
  private options: Required<PreloadOptions>;

  // 用户行为追踪
  private accessHistory: string[] = [];
  private accessPatterns: Map<string, string[]> = new Map();

  constructor(options: PreloadOptions = {}) {
    this.options = {
      maxConcurrent: options.maxConcurrent ?? 3,
      timeout: options.timeout ?? 10000,
      retryOnError: options.retryOnError ?? false,
    };
  }

  /**
   * 添加预加载任务
   */
  addTask(task: Omit<PreloadTask, 'id'>): string {
    const id = this.generateTaskId();
    const preloadTask: PreloadTask = { ...task, id };

    this.queue.push(preloadTask);
    this.sortQueue();

    console.log(`预加载任务已添加: ${task.key}, 优先级: ${task.priority}`);

    return id;
  }

  /**
   * 批量添加任务
   */
  addTasks(tasks: Omit<PreloadTask, 'id'>[]): string[] {
    return tasks.map(task => this.addTask(task));
  }

  /**
   * 开始处理预加载队列
   */
  async process(): Promise<void> {
    while (this.queue.length > 0 && this.processing.size < this.options.maxConcurrent) {
      const task = this.queue.shift();
      if (!task) break;

      // 检查依赖
      if (task.dependencies && !this.areDependenciesCompleted(task.dependencies)) {
        // 依赖未完成，放回队列末尾
        this.queue.push(task);
        continue;
      }

      this.processTask(task);
    }
  }

  /**
   * 处理单个任务
   */
  private async processTask(task: PreloadTask): Promise<void> {
    this.processing.add(task.id);

    try {
      await this.executeWithTimeout(task.loader, this.options.timeout);
      this.completed.add(task.id);
      console.log(`预加载成功: ${task.key}`);
    } catch (error) {
      console.error(`预加载失败: ${task.key}`, error);
      this.failed.add(task.id);

      // 重试
      if (this.options.retryOnError) {
        console.log(`重试预加载: ${task.key}`);
        this.queue.push(task);
      }
    } finally {
      this.processing.delete(task.id);

      // 继续处理队列
      this.process();
    }
  }

  /**
   * 带超时的执行
   */
  private executeWithTimeout<T>(
    fn: () => Promise<T>,
    timeout: number
  ): Promise<T> {
    return Promise.race([
      fn(),
      new Promise<T>((_, reject) =>
        setTimeout(() => reject(new Error('预加载超时')), timeout)
      ),
    ]);
  }

  /**
   * 检查依赖是否完成
   */
  private areDependenciesCompleted(dependencies: string[]): boolean {
    return dependencies.every(dep => this.completed.has(dep));
  }

  /**
   * 队列排序（按优先级）
   */
  private sortQueue(): void {
    this.queue.sort((a, b) => b.priority - a.priority);
  }

  /**
   * 记录访问
   */
  recordAccess(key: string): void {
    this.accessHistory.push(key);

    // 保持历史记录在合理范围内
    if (this.accessHistory.length > 100) {
      this.accessHistory.shift();
    }

    // 更新访问模式
    this.updateAccessPatterns();
  }

  /**
   * 更新访问模式
   */
  private updateAccessPatterns(): void {
    // 获取最近的访问
    const recentAccess = this.accessHistory.slice(-5);

    for (let i = 0; i < recentAccess.length - 1; i++) {
      const key = recentAccess[i];
      const next = recentAccess[i + 1];

      if (!this.accessPatterns.has(key)) {
        this.accessPatterns.set(key, []);
      }

      const pattern = this.accessPatterns.get(key)!;
      if (!pattern.includes(next)) {
        pattern.push(next);
      }
    }
  }

  /**
   * 预测下一步可能访问的资源
   */
  predictNext(currentKey: string): string[] {
    const pattern = this.accessPatterns.get(currentKey);
    return pattern || [];
  }

  /**
   * 智能预加载
   */
  async smartPreload(
    currentKey: string,
    loaders: Map<string, () => Promise<unknown>>
  ): Promise<void> {
    const predictions = this.predictNext(currentKey);

    for (const key of predictions) {
      const loader = loaders.get(key);
      if (loader && !this.completed.has(key)) {
        this.addTask({
          key,
          loader,
          priority: 5, // 中等优先级
          estimatedTime: 1000,
        });
      }
    }

    await this.process();
  }

  /**
   * 获取状态
   */
  getStatus(): {
    queueSize: number;
    processing: number;
    completed: number;
    failed: number;
  } {
    return {
      queueSize: this.queue.length,
      processing: this.processing.size,
      completed: this.completed.size,
      failed: this.failed.size,
    };
  }

  /**
   * 清空队列
   */
  clear(): void {
    this.queue = [];
    this.processing.clear();
  }

  /**
   * 重置统计
   */
  reset(): void {
    this.queue = [];
    this.processing.clear();
    this.completed.clear();
    this.failed.clear();
  }

  /**
   * 生成任务ID
   */
  private generateTaskId(): string {
    return `preload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}
