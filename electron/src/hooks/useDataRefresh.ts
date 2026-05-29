import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * 数据刷新选项
 */
export interface RefreshOptions {
  /** 刷新间隔（毫秒），默认5000ms */
  interval?: number;
  /** 是否启用自动刷新，默认true */
  enabled?: boolean;
  /** 刷新回调函数 */
  onRefresh?: () => Promise<void>;
  /** 错误处理回调 */
  onError?: (error: Error) => void;
  /** 是否立即执行一次刷新，默认true */
  immediate?: boolean;
}

/**
 * 数据刷新Hook返回值
 */
export interface UseDataRefreshReturn {
  /** 是否正在刷新 */
  refreshing: boolean;
  /** 最后刷新时间 */
  lastRefreshTime: number | null;
  /** 手动刷新函数 */
  refresh: () => Promise<void>;
  /** 错误信息 */
  error: Error | null;
}

/**
 * 数据刷新Hook
 * 提供自动和手动刷新功能
 *
 * @example
 * ```tsx
 * const { refreshing, refresh, lastRefreshTime } = useDataRefresh({
 *   interval: 5000,
 *   onRefresh: async () => {
 *     await fetchData();
 *   },
 *   onError: (error) => {
 *     console.error('刷新失败:', error);
 *   }
 * });
 * ```
 */
export function useDataRefresh({
  interval = 5000,
  enabled = true,
  onRefresh,
  onError,
  immediate = true,
}: RefreshOptions = {}): UseDataRefreshReturn {
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<number | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // 手动刷新
  const refresh = useCallback(async () => {
    if (refreshing || !onRefresh) return;

    setRefreshing(true);
    setError(null);

    try {
      await onRefresh();
      if (mountedRef.current) {
        setLastRefreshTime(Date.now());
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('刷新失败');
      if (mountedRef.current) {
        setError(error);
      }
      onError?.(error);
    } finally {
      if (mountedRef.current) {
        setRefreshing(false);
      }
    }
  }, [refreshing, onRefresh, onError]);

  // 立即执行一次
  useEffect(() => {
    if (immediate && onRefresh) {
      refresh();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 自动刷新
  useEffect(() => {
    if (!enabled || !onRefresh) {
      return;
    }

    // 清除旧的定时器
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    // 设置新的定时器
    timerRef.current = setInterval(() => {
      if (!refreshing) {
        refresh();
      }
    }, interval);

    // 清理函数
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [enabled, interval, refresh, refreshing, onRefresh]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  return {
    refreshing,
    lastRefreshTime,
    refresh,
    error,
  };
}
