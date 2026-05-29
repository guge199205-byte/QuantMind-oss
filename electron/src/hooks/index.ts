/**
 * Hooks导出
 */

// 防抖节流
export {
  useDebounce,
  useDebouncedCallback,
  useThrottle,
  useThrottledCallback,
  useDebounceWithImmediate
} from './useDebounce';

// 懒加载
export {
  lazyWithRetry,
  preloadComponent,
  preloadComponents,
  lazyIf,
  lazyWithDelay,
  lazyWithLoader,
  createLazyRoutes,
  SmartPreloader,
  globalPreloader
} from './useLazyLoad';

export type { LazyRouteConfig } from './useLazyLoad';

// 数据刷新（已存在）
export { useDataRefresh } from './useDataRefresh';
