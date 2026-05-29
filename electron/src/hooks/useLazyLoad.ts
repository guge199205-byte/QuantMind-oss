import { lazy, ComponentType, LazyExoticComponent } from 'react';

/**
 * 懒加载工具
 * 用于动态导入组件
 */

/**
 * 带重试的懒加载
 */
export function lazyWithRetry<T extends ComponentType<unknown>>(
  importFunc: () => Promise<{ default: T }>,
  retries: number = 3,
  interval: number = 1000
): LazyExoticComponent<T> {
  return lazy(() => {
    return new Promise<{ default: T }>((resolve, reject) => {
      const attemptImport = (retriesLeft: number) => {
        importFunc()
          .then(resolve)
          .catch((error) => {
            if (retriesLeft === 0) {
              reject(error);
              return;
            }

            console.log(`Import failed, retrying... (${retriesLeft} retries left)`);
            setTimeout(() => {
              attemptImport(retriesLeft - 1);
            }, interval);
          });
      };

      attemptImport(retries);
    });
  });
}

/**
 * 预加载组件
 */
export function preloadComponent<T extends ComponentType<unknown>>(
  importFunc: () => Promise<{ default: T }>
): Promise<{ default: T }> {
  return importFunc();
}

/**
 * 批量预加载
 */
export async function preloadComponents(
  importFuncs: Array<() => Promise<unknown>>
): Promise<void> {
  await Promise.all(importFuncs.map((importFunc) => importFunc()));
}

/**
 * 条件懒加载
 */
export function lazyIf<T extends ComponentType<unknown>>(
  condition: boolean,
  importFunc: () => Promise<{ default: T }>,
  fallback: T
): LazyExoticComponent<T> | T {
  if (condition) {
    return lazy(importFunc);
  }
  return fallback;
}

/**
 * 延迟懒加载
 */
export function lazyWithDelay<T extends ComponentType<unknown>>(
  importFunc: () => Promise<{ default: T }>,
  delay: number = 0
): LazyExoticComponent<T> {
  return lazy(() => {
    return new Promise<{ default: T }>((resolve) => {
      setTimeout(() => {
        importFunc().then(resolve);
      }, delay);
    });
  });
}

/**
 * 带加载器的懒加载
 */
export function lazyWithLoader<T extends ComponentType<unknown>>(
  importFunc: () => Promise<{ default: T }>,
  onLoadStart?: () => void,
  onLoadEnd?: () => void
): LazyExoticComponent<T> {
  return lazy(() => {
    onLoadStart?.();
    return importFunc().finally(() => {
      onLoadEnd?.();
    });
  });
}

/**
 * 路由懒加载配置
 */
export interface LazyRouteConfig {
  path: string;
  component: () => Promise<{ default: ComponentType<unknown> }>;
  preload?: boolean;
  retries?: number;
}

export function createLazyRoutes(configs: LazyRouteConfig[]) {
  return configs.map((config) => ({
    ...config,
    component: lazyWithRetry(config.component, config.retries)
  }));
}

/**
 * 智能预加载
 * 基于用户行为预测和预加载组件
 */
export class SmartPreloader {
  private preloadQueue: Map<string, () => Promise<unknown>> = new Map();
  private loadedComponents: Set<string> = new Set();

  register(key: string, importFunc: () => Promise<unknown>) {
    this.preloadQueue.set(key, importFunc);
  }

  async preload(key: string): Promise<void> {
    if (this.loadedComponents.has(key)) {
      return;
    }

    const importFunc = this.preloadQueue.get(key);
    if (importFunc) {
      await importFunc();
      this.loadedComponents.add(key);
    }
  }

  async preloadAll(): Promise<void> {
    const promises = Array.from(this.preloadQueue.entries())
      .filter(([key]) => !this.loadedComponents.has(key))
      .map(([key]) => this.preload(key));

    await Promise.all(promises);
  }

  async preloadByPriority(priorities: string[]): Promise<void> {
    for (const key of priorities) {
      await this.preload(key);
    }
  }

  isLoaded(key: string): boolean {
    return this.loadedComponents.has(key);
  }

  clear(): void {
    this.preloadQueue.clear();
    this.loadedComponents.clear();
  }
}

// 全局预加载器实例
export const globalPreloader = new SmartPreloader();

export default {
  lazyWithRetry,
  preloadComponent,
  preloadComponents,
  lazyIf,
  lazyWithDelay,
  lazyWithLoader,
  createLazyRoutes,
  SmartPreloader,
  globalPreloader
};
