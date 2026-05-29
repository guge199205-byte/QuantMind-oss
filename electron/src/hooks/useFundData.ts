import { useState, useEffect, useCallback, useRef } from 'react';
import { FundData } from '../services/userService';
import { portfolioService } from '../services/portfolioService';
import { shouldUpdateByFingerprint } from '../utils/dataChange';
import { refreshOrchestrator } from '../services/refreshOrchestrator';
import { useAppSelector } from '../store';
import { authService } from '../features/auth/services/authService';

export interface UseFundDataOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
  userId?: string;
  tenantId?: string;
}

export interface UseFundDataReturn {
  data: FundData | null;
  loading: boolean;
  error: string | null;
  lastUpdate: string | null;
  isSimulated: boolean;
  tradingMode: 'real' | 'simulation';
  refresh: () => Promise<void>;
}

export const useFundData = (options: UseFundDataOptions = {}): UseFundDataReturn => {
  const {
    autoRefresh = true,
    refreshInterval = 30000,
    userId,
    tenantId,
  } = options;

  const tradingMode = useAppSelector((state) => state.ui.tradingMode);
  const [data, setData] = useState<FundData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [isSimulated, setIsSimulated] = useState<boolean>(tradingMode === 'simulation');
  const fingerprintRef = useRef<string | null>(null);
  const initializedRef = useRef<boolean>(false);

  const storedUser = authService.getStoredUser() as { id?: string; user_id?: string; tenant_id?: string } | null;
  const resolvedUserId = String(
    userId ||
    storedUser?.user_id ||
    storedUser?.id ||
    ''
  ).trim();
  const resolvedTenantId = String(
    tenantId ||
    storedUser?.tenant_id ||
    localStorage.getItem('tenant_id') ||
    (import.meta as any).env?.VITE_TENANT_ID ||
    'default'
  ).trim() || 'default';

  // 获取资金数据
  const fetchData = useCallback(async (params?: { silent?: boolean }) => {
    const silent = params?.silent ?? true;

    try {
      setLoading(true);
      setError(null);

      const result = await portfolioService.getFundOverview(resolvedUserId, tradingMode, resolvedTenantId);

      const nextSnapshot = {
        data: result.data,
        isSimulated: result.isSimulated,
        mode: tradingMode
      };

      const { changed, fingerprint } = shouldUpdateByFingerprint(fingerprintRef.current, nextSnapshot);

      if (!changed) {
        return;
      }

      setData(result.data);
      setIsSimulated(result.isSimulated);
      setLastUpdate(result.data.lastUpdate);
      fingerprintRef.current = fingerprint;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '未知错误';
      setError(errorMessage);
      console.error('获取资金数据失败:', errorMessage);

      // 降级：使用默认数据
      const defaultData = portfolioService.getDefaultFundData();
      const nextSnapshot = {
        data: defaultData,
        isSimulated: true,
      };

      const { changed, fingerprint } = shouldUpdateByFingerprint(fingerprintRef.current, nextSnapshot);
      if (changed) {
        setData(defaultData);
        setIsSimulated(true);
        setLastUpdate(defaultData.lastUpdate);
        fingerprintRef.current = fingerprint;
      }
    } finally {
      initializedRef.current = true;
      setLoading(false);
    }
  }, [resolvedUserId, resolvedTenantId, tradingMode]);

  // 手动刷新
  const refresh = useCallback(async () => {
    await fetchData({ silent: true });
  }, [fetchData]);

  // 初始化
  useEffect(() => {
    fetchData({ silent: false });
  }, [fetchData]);

  // 监听模式切换，立即进入加载状态并重置数据
  useEffect(() => {
    setLoading(true);
    setData(null);
    fingerprintRef.current = null;
  }, [tradingMode]);

  // 统一由协调器触发刷新，避免模块自轮询造成闪烁
  useEffect(() => {
    if (!autoRefresh) {
      return;
    }

    const unregister = refreshOrchestrator.register(
      'fund',
      async () => {
        await fetchData({ silent: true });
      },
      { minIntervalMs: Math.min(Math.max(refreshInterval, 800), 5000) },
    );

    return unregister;
  }, [autoRefresh, refreshInterval, fetchData]);

  return {
    data,
    loading,
    error,
    lastUpdate,
    isSimulated,
    tradingMode,
    refresh,
  };
};
