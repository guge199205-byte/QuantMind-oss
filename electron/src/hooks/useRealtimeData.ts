import { useState, useEffect, useCallback, useRef } from 'react';

export interface RealtimeDataOptions {
  enabled?: boolean;
  interval?: number;
  onUpdate?: (data: unknown) => void;
  onError?: (error: string) => void;
}

export interface RealtimeDataReturn {
  isConnected: boolean;
  lastUpdate: string | null;
  connectionCount: number;
  start: () => void;
  stop: () => void;
  toggle: () => void;
}

export const useRealtimeData = (options: RealtimeDataOptions = {}): RealtimeDataReturn => {
  const {
    enabled = true,
    interval = 10000,
    onUpdate,
    onError
  } = options;

  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [connectionCount, setConnectionCount] = useState<number>(0);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isEnabledRef = useRef<boolean>(enabled);

  // 更新连接状态的方法
  const updateConnection = useCallback((connected: boolean) => {
    setIsConnected(connected);
    if (connected) {
      setLastUpdate(new Date().toISOString());
      setConnectionCount(((prev: number) => prev + 1) as any);
    }
  }, []);

  // 启动实时数据更新
  const start = useCallback(() => {
    if (intervalRef.current) return; // 已经在运行

    console.log('启动实时数据更新');

    const fetchData = async () => {
      try {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 100));

        // 模拟数据
        const mockData = {
          timestamp: new Date().toISOString(),
          market: {
            status: 'open',
            indices: Math.random() > 0.1 // 90%成功率
          },
          user: {
            online: true
          }
        };

        updateConnection(true);
        onUpdate?.(mockData);

      } catch (error) {
        console.error('实时数据更新失败:', error);
        updateConnection(false);
        onError?.(error instanceof Error ? error.message : '未知错误');
      }
    };

    // 立即执行一次
    fetchData();

    // 设置定时器
    intervalRef.current = setInterval(fetchData, interval);

  }, [interval, onUpdate, onError, updateConnection]);

  // 停止实时数据更新
  const stop = useCallback(() => {
    if (intervalRef.current) {
      console.log('停止实时数据更新');
      clearInterval(intervalRef.current);
      intervalRef.current = null;
      setIsConnected(false);
    }
  }, []);

  // 切换实时数据更新状态
  const toggle = useCallback(() => {
    if (isConnected) {
      stop();
    } else {
      start();
    }
  }, [isConnected, start, stop]);

  // 根据enabled参数自动启动/停止
  useEffect(() => {
    isEnabledRef.current = enabled;

    if (enabled) {
      start();
    } else {
      stop();
    }

    return () => {
      stop();
    };
  }, [enabled, start, stop]);

  return {
    isConnected,
    lastUpdate,
    connectionCount,
    start,
    stop,
    toggle
  };
};
