import { useQuery } from '@tanstack/react-query';
import { marketService, MarketOverviewResponse } from '../services/marketService';

export interface UseMarketDataOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
  mockData?: boolean;
}

export interface UseMarketDataReturn {
  data: MarketOverviewResponse | null;
  loading: boolean;
  error: string | null;
  lastUpdate: string | null;
  refresh: () => void;
  isConnected: boolean;
}

export const useMarketData = (options: UseMarketDataOptions = {}): UseMarketDataReturn => {
  const {
    autoRefresh = true,
    refreshInterval = 10000, // 10秒
    mockData = false
  } = options;

  const { data, error, isLoading, isError, refetch } = useQuery<MarketOverviewResponse, Error>({
    queryKey: ['marketData', mockData],
    queryFn: async () => {
      if (mockData) {
        return marketService.generateMockData();
      }
      const response = await marketService.getMarketOverview();
      if (!response.success) {
        throw new Error(response.error || '获取数据失败');
      }
      return response.data!;
    },
    refetchInterval: autoRefresh ? refreshInterval : false,
    refetchOnWindowFocus: true,
  });

  return {
    data: data || null,
    loading: isLoading,
    error: error ? error.message : null,
    lastUpdate: data ? new Date().toISOString() : null,
    refresh: refetch,
    isConnected: !isError,
  };
};
