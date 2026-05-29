/**
 * 速率限制器
 */

export interface RateLimiterOptions {
  maxTokens?: number;
  minInterval?: number; // ms
}

export class RateLimiter {
  private requests: number[] = [];
  private readonly maxRequests: number;
  private readonly timeWindow: number;

  constructor(maxRequestsOrOptions: number | RateLimiterOptions, timeWindow?: number) {
    if (typeof maxRequestsOrOptions === 'number') {
      this.maxRequests = maxRequestsOrOptions;
      this.timeWindow = typeof timeWindow === 'number' ? timeWindow : 1000;
    } else {
      const opts = maxRequestsOrOptions || {};
      // 对象式构造：将 maxTokens/minInterval 映射为 maxRequests/timeWindow
      this.maxRequests = opts.maxTokens ?? 20;
      this.timeWindow = opts.minInterval ?? 1000;
    }
  }

  /**
   * 检查是否可以进行请求
   */
  public canMakeRequest(): boolean {
    const now = Date.now();

    // 清除时间窗口外的请求记录
    this.requests = this.requests.filter(time => now - time < this.timeWindow);

    // 检查是否超过限制
    if (this.requests.length >= this.maxRequests) {
      return false;
    }

    // 记录当前请求
    this.requests.push(now);
    return true;
  }

  /**
   * 等待直到可以进行请求
   */
  public async waitForRequest(): Promise<void> {
    while (!this.canMakeRequest()) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  /** 兼容老代码命名： acquire 等价于 waitForRequest */
  public async acquire(): Promise<void> {
    return this.waitForRequest();
  }
}
