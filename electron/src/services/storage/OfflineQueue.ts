/**
 * 离线队列服务
 * 用于在离线时缓存请求，在线后自动重放
 */

export interface QueuedRequest {
  id: string;
  method: string;
  url: string;
  data?: unknown;
  timestamp: number;
  retries: number;
  priority: number;
}

export interface QueueOptions {
  maxRetries?: number;
  retryDelay?: number;
  maxQueueSize?: number;
}

export class OfflineQueue {
  private queue: QueuedRequest[] = [];
  private processing: boolean = false;
  private isOnline: boolean = navigator.onLine;
  private readonly storageKey = 'offline_queue';
  private readonly options: Required<QueueOptions>;

  constructor(options: QueueOptions = {}) {
    this.options = {
      maxRetries: options.maxRetries ?? 3,
      retryDelay: options.retryDelay ?? 1000,
      maxQueueSize: options.maxQueueSize ?? 100,
    };

    this.loadQueue();
    this.setupListeners();
  }

  /**
   * 添加请求到队列
   */
  enqueue(request: Omit<QueuedRequest, 'id' | 'timestamp' | 'retries'>): void {
    // 检查队列大小
    if (this.queue.length >= this.options.maxQueueSize) {
      console.warn('离线队列已满，移除最旧的请求');
      this.queue.shift();
    }

    const queuedRequest: QueuedRequest = {
      ...request,
      id: this.generateId(),
      timestamp: Date.now(),
      retries: 0,
      priority: request.priority ?? 0,
    };

    this.queue.push(queuedRequest);
    this.sortQueue();
    this.saveQueue();

    console.log(`请求已加入离线队列: ${queuedRequest.id}`);
  }

  /**
   * 处理队列
   */
  async processQueue(): Promise<void> {
    if (this.processing || !this.isOnline || this.queue.length === 0) {
      return;
    }

    this.processing = true;
    console.log(`开始处理离线队列，共 ${this.queue.length} 个请求`);

    const processed: string[] = [];
    const failed: QueuedRequest[] = [];

    for (const request of this.queue) {
      try {
        await this.executeRequest(request);
        processed.push(request.id);
        console.log(`请求处理成功: ${request.id}`);
      } catch (error) {
        console.error(`请求处理失败: ${request.id}`, error);

        // 增加重试次数
        request.retries++;

        if (request.retries < this.options.maxRetries) {
          failed.push(request);
          console.log(`请求将重试: ${request.id}, 重试次数: ${request.retries}`);
        } else {
          console.error(`请求已达到最大重试次数，放弃: ${request.id}`);
        }
      }

      // 重试延迟
      if (failed.length > 0) {
        await this.sleep(this.options.retryDelay);
      }
    }

    // 更新队列：移除成功的，保留失败的
    this.queue = failed;
    this.saveQueue();

    this.processing = false;
    console.log(`队列处理完成，成功: ${processed.length}, 失败: ${failed.length}`);
  }

  /**
   * 执行请求
   */
  private async executeRequest(request: QueuedRequest): Promise<unknown> {
    const options: RequestInit = {
      method: request.method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (request.data) {
      options.body = JSON.stringify(request.data);
    }

    const response = await fetch(request.url, options);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json() as Promise<unknown>;
  }

  /**
   * 获取队列状态
   */
  getStatus(): {
    queueSize: number;
    processing: boolean;
    isOnline: boolean;
    requests: QueuedRequest[];
  } {
    return {
      queueSize: this.queue.length,
      processing: this.processing,
      isOnline: this.isOnline,
      requests: [...this.queue],
    };
  }

  /**
   * 清空队列
   */
  clearQueue(): void {
    this.queue = [];
    this.saveQueue();
    console.log('离线队列已清空');
  }

  /**
   * 移除指定请求
   */
  removeRequest(id: string): boolean {
    const index = this.queue.findIndex(req => req.id === id);
    if (index !== -1) {
      this.queue.splice(index, 1);
      this.saveQueue();
      return true;
    }
    return false;
  }

  /**
   * 对队列排序（按优先级和时间）
   */
  private sortQueue(): void {
    this.queue.sort((a, b) => {
      // 优先级高的在前
      if (a.priority !== b.priority) {
        return b.priority - a.priority;
      }
      // 时间早的在前
      return a.timestamp - b.timestamp;
    });
  }

  /**
   * 设置监听器
   */
  private setupListeners(): void {
    window.addEventListener('online', () => {
      this.isOnline = true;
      console.log('网络已恢复，开始处理离线队列');
      this.processQueue();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
      console.log('网络已断开，进入离线模式');
    });
  }

  /**
   * 保存队列到localStorage
   */
  private saveQueue(): void {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.queue));
    } catch (error: unknown) {
      console.error('保存离线队列失败:', (error as Error).message ?? error);
    }
  }

  /**
   * 从localStorage加载队列
   */
  private loadQueue(): void {
    try {
      const saved = localStorage.getItem(this.storageKey);
      if (saved) {
        this.queue = JSON.parse(saved);
        console.log(`已加载 ${this.queue.length} 个离线请求`);
      }
    } catch (error: unknown) {
      console.error('加载离线队列失败:', (error as Error).message ?? error);
    }
  }

  /**
   * 生成唯一ID
   */
  private generateId(): string {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * 延迟函数
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
