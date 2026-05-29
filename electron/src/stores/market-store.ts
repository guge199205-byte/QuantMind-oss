/**
 * 市场数据状态管理
 *
 * 使用Zustand管理市场数据、技术指标等状态
 *
 * @author QuantMind Team
 * @date 2025-11-12
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import {
  MarketQuote,
  IndicatorResponse,
  MarketDataParams,
  IndicatorParams,
} from '../types/market';
import { getAPIClient } from '../services';

/**
 * 市场数据状态接口
 */
export interface MarketState {
  // 数据状态
  quotes: Record<string, MarketQuote>;
  indicators: Record<string, IndicatorResponse>;
  watchlist: string[];

  // 加载状态
  loading: boolean;
  loadingQuotes: Record<string, boolean>;
  loadingIndicators: Record<string, boolean>;

  // 错误状态
  error: Error | null;
  errors: Record<string, Error>;

  // 缓存和更新时间
  lastUpdate: Record<string, number>;
  cacheExpiry: number; // 缓存过期时间（毫秒）

  // Actions
  fetchMarketData: (params: MarketDataParams) => Promise<void>;
  fetchRealtimeQuote: (symbol: string) => Promise<void>;
  fetchIndicators: (params: IndicatorParams) => Promise<void>;
  batchFetchIndicators: (symbols: string[], indicators: string[]) => Promise<void>;

  // 自选股管理
  addToWatchlist: (symbol: string) => void;
  removeFromWatchlist: (symbol: string) => void;
  setWatchlist: (symbols: string[]) => void;

  // 缓存管理
  clearCache: () => void;
  clearError: () => void;
  clearSymbolError: (symbol: string) => void;
  isDataStale: (key: string) => boolean;

  // 刷新
  refreshAll: () => Promise<void>;
}

/**
 * 创建市场数据状态管理
 */
export const useMarketStore = create<MarketState>()(
  devtools(
    (set, get) => ({
      // 初始状态
      quotes: {},
      indicators: {},
      watchlist: [],
      loading: false,
      loadingQuotes: {},
      loadingIndicators: {},
      error: null,
      errors: {},
      lastUpdate: {},
      cacheExpiry: 60000, // 默认1分钟过期

      // 获取市场数据
      fetchMarketData: async (params) => {
        const cacheKey = `market-${params.symbols.join(',')}`;

        // 检查缓存是否过期
        if (!get().isDataStale(cacheKey)) {
          return;
        }

        set({ loading: true, error: null });

        try {
          const apiClient = getAPIClient();
          const response = await apiClient.get<any>('/api/v1/quotes/', {
            symbols: params.symbols.join(','),
          });

          // 更新状态
          const newQuotes = { ...get().quotes };
          const data = response.quotes || response.data || [];
          data.forEach((quote: any) => {
            newQuotes[quote.symbol] = quote;
          });

          set({
            quotes: newQuotes,
            loading: false,
            lastUpdate: {
              ...get().lastUpdate,
              [cacheKey]: Date.now(),
            },
          });
        } catch (error: any) {
          set({
            loading: false,
            error: error,
          });
          throw error;
        }
      },

      // 获取单个股票实时行情
      fetchRealtimeQuote: async (symbol) => {
        const cacheKey = `quote-${symbol}`;

        // 检查缓存
        if (!get().isDataStale(cacheKey)) {
          return;
        }

        set({
          loadingQuotes: {
            ...get().loadingQuotes,
            [symbol]: true,
          },
        });

        try {
          const apiClient = getAPIClient();
          const quote = await apiClient.get<MarketQuote>(`/api/v1/quotes/${symbol}`);

          set({
            quotes: {
              ...get().quotes,
              [symbol]: quote,
            },
            loadingQuotes: {
              ...get().loadingQuotes,
              [symbol]: false,
            },
            lastUpdate: {
              ...get().lastUpdate,
              [cacheKey]: Date.now(),
            },
          });
        } catch (error: any) {
          set({
            loadingQuotes: {
              ...get().loadingQuotes,
              [symbol]: false,
            },
            errors: {
              ...get().errors,
              [symbol]: error,
            },
          });
          throw error;
        }
      },

      // 计算技术指标
      fetchIndicators: async (params) => {
        const { symbol, indicators: indicatorList } = params;
        const cacheKey = `indicators-${symbol}-${indicatorList.join(',')}`;

        // 检查缓存
        if (!get().isDataStale(cacheKey)) {
          return;
        }

        set({
          loadingIndicators: {
            ...get().loadingIndicators,
            [symbol]: true,
          },
        });

        try {
          const apiClient = getAPIClient();
          // 注意：指标计算可能由 engine 负责
          const result = await apiClient.post<IndicatorResponse>(`/api/v1/inference/indicators`, params as any);

          set({
            indicators: {
              ...get().indicators,
              [symbol]: result,
            },
            loadingIndicators: {
              ...get().loadingIndicators,
              [symbol]: false,
            },
            lastUpdate: {
              ...get().lastUpdate,
              [cacheKey]: Date.now(),
            },
          });
        } catch (error: any) {
          set({
            loadingIndicators: {
              ...get().loadingIndicators,
              [symbol]: false,
            },
            errors: {
              ...get().errors,
              [`indicators-${symbol}`]: error,
            },
          });
          throw error;
        }
      },

      // 批量计算技术指标
      batchFetchIndicators: async (symbols, indicators) => {
        set({ loading: true, error: null });

        try {
          const apiClient = getAPIClient();
          const response = await apiClient.post<any>(`/api/v1/inference/indicators/batch`, {
            symbols,
            indicators,
          });

          const newIndicators = { ...get().indicators };
          const results = response.results || [];
          results.forEach((result: any) => {
            newIndicators[result.symbol] = result;
          });

          set({
            indicators: newIndicators,
            loading: false,
            lastUpdate: {
              ...get().lastUpdate,
              [`batch-indicators-${Date.now()}`]: Date.now(),
            },
          });
        } catch (error: any) {
          set({
            loading: false,
            error: error,
          });
          throw error;
        }
      },

      // 添加自选股
      addToWatchlist: (symbol) => {
        const watchlist = get().watchlist;
        if (!watchlist.includes(symbol)) {
          set({
            watchlist: [...watchlist, symbol],
          });
        }
      },

      // 移除自选股
      removeFromWatchlist: (symbol) => {
        set({
          watchlist: get().watchlist.filter((s) => s !== symbol),
        });
      },

      // 设置自选股列表
      setWatchlist: (symbols) => {
        set({ watchlist: symbols });
      },

      // 清除所有缓存
      clearCache: () => {
        set({
          quotes: {},
          indicators: {},
          lastUpdate: {},
          error: null,
          errors: {},
        });
      },

      // 清除全局错误
      clearError: () => {
        set({ error: null });
      },

      // 清除特定股票的错误
      clearSymbolError: (symbol) => {
        const errors = { ...get().errors };
        delete errors[symbol];
        delete errors[`indicators-${symbol}`];
        set({ errors });
      },

      // 检查数据是否过期
      isDataStale: (key) => {
        const lastUpdate = get().lastUpdate[key];
        if (!lastUpdate) return true;

        const age = Date.now() - lastUpdate;
        return age > get().cacheExpiry;
      },

      // 刷新所有数据
      refreshAll: async () => {
        const { watchlist } = get();

        if (watchlist.length === 0) {
          return;
        }

        set({ loading: true, error: null });

        try {
          const apiClient = getAPIClient();
          const response = await apiClient.get<any>('/api/v1/quotes/', {
            symbols: watchlist.join(','),
          });

          const newQuotes = { ...get().quotes };
          const data = response.quotes || response.data || [];
          data.forEach((quote: any) => {
            newQuotes[quote.symbol] = quote;
          });

          set({
            quotes: newQuotes,
            loading: false,
            lastUpdate: {
              ...get().lastUpdate,
              'refresh-all': Date.now(),
            },
          });
        } catch (error: any) {
          set({
            loading: false,
            error: error,
          });
          throw error;
        }
      },
    }),
    {
      name: 'market-store',
    }
  )
);

/**
 * 用于清理store的hook
 */
export const useMarketStoreCleanup = () => {
  return () => {
    useMarketStore.getState().clearCache();
  };
};
