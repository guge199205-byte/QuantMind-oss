import { useEffect, useState, useRef, useCallback } from 'react';

/**
 * 防抖Hook
 * 延迟执行函数，在指定时间内只执行最后一次
 */

export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * 防抖函数Hook
 * 返回一个防抖后的函数
 */
export function useDebouncedCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number = 300
): (...args: Parameters<T>) => void {
  const timeoutRef = useRef<NodeJS.Timeout>();
  const callbackRef = useRef(callback);

  // 更新回调引用
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args);
      }, delay);
    },
    [delay]
  );
}

/**
 * 节流Hook
 * 在指定时间内最多执行一次
 */
export function useThrottle<T>(value: T, interval: number = 300): T {
  const [throttledValue, setThrottledValue] = useState<T>(value);
  const lastExecuted = useRef<number>(Date.now());

  useEffect(() => {
    const now = Date.now();
    const timeSinceLastExecution = now - lastExecuted.current;

    if (timeSinceLastExecution >= interval) {
      setThrottledValue(value);
      lastExecuted.current = now;
    } else {
      const timer = setTimeout(() => {
        setThrottledValue(value);
        lastExecuted.current = Date.now();
      }, interval - timeSinceLastExecution);

      return () => clearTimeout(timer);
    }
  }, [value, interval]);

  return throttledValue;
}

/**
 * 节流函数Hook
 * 返回一个节流后的函数
 */
export function useThrottledCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  interval: number = 300
): (...args: Parameters<T>) => void {
  const lastExecuted = useRef<number>(0);
  const timeoutRef = useRef<NodeJS.Timeout>();
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return useCallback(
    (...args: Parameters<T>) => {
      const now = Date.now();
      const timeSinceLastExecution = now - lastExecuted.current;

      if (timeSinceLastExecution >= interval) {
        callbackRef.current(...args);
        lastExecuted.current = now;
      } else {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }

        timeoutRef.current = setTimeout(() => {
          callbackRef.current(...args);
          lastExecuted.current = Date.now();
        }, interval - timeSinceLastExecution);
      }
    },
    [interval]
  );
}

/**
 * 组合防抖和立即执行
 * 第一次立即执行，后续调用防抖
 */
export function useDebounceWithImmediate<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number = 300,
  immediate: boolean = true
): (...args: Parameters<T>) => void {
  const timeoutRef = useRef<NodeJS.Timeout>();
  const callbackRef = useRef(callback);
  const hasCalledRef = useRef(false);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return useCallback(
    (...args: Parameters<T>) => {
      const shouldCallImmediately = immediate && !hasCalledRef.current;

      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      if (shouldCallImmediately) {
        callbackRef.current(...args);
        hasCalledRef.current = true;
      }

      timeoutRef.current = setTimeout(() => {
        if (!shouldCallImmediately) {
          callbackRef.current(...args);
        }
        hasCalledRef.current = false;
      }, delay);
    },
    [delay, immediate]
  );
}

export default {
  useDebounce,
  useDebouncedCallback,
  useThrottle,
  useThrottledCallback,
  useDebounceWithImmediate
};
