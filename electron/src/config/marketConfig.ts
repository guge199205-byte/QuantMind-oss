/**
 * 多市场配置
 *
 * 为各页面提供市场特定的默认值（Qlib region、股票池、基准指数等）
 */

import type { AppMarket } from '../store/slices/uiSlice';

export interface MarketConfig {
  /** 市场显示名称 */
  label: string;
  /** Qlib region 参数 */
  qlibRegion: string;
  /** Qlib provider URI */
  qlibProviderUri: string;
  /** 默认股票池名称 */
  defaultUniverse: string;
  /** 基准指数代码 */
  benchmark: string;
  /** 基准指数名称 */
  benchmarkName: string;
  /** 货币符号 */
  currency: string;
  /** 交易日历标识 */
  calendar: string;
  /** 后端 market adapter ID */
  adapterId: string;
}

export const MARKET_CONFIGS: Record<AppMarket, MarketConfig> = {
  CN: {
    label: 'A股',
    qlibRegion: 'cn',
    qlibProviderUri: 'db/qlib_data',
    defaultUniverse: 'csi300',
    benchmark: 'SH000300',
    benchmarkName: '沪深300',
    currency: 'CNY',
    calendar: 'SSE',
    adapterId: 'a_share',
  },
  HK: {
    label: '港股',
    qlibRegion: 'hk',
    qlibProviderUri: 'db/qlib_data/hk_data',
    defaultUniverse: 'all',
    benchmark: 'HSI',
    benchmarkName: '恒生指数',
    currency: 'HKD',
    calendar: 'HKEX',
    adapterId: 'hong_kong',
  },
  US: {
    label: '美股',
    qlibRegion: 'us',
    qlibProviderUri: 'db/qlib_data/us_data',
    defaultUniverse: 'all',
    benchmark: 'SPX',
    benchmarkName: '标普500',
    currency: 'USD',
    calendar: 'NYSE',
    adapterId: 'us_stock',
  },
  CRYPTO: {
    label: '区块链',
    qlibRegion: 'crypto',
    qlibProviderUri: 'db/qlib_data/crypto_data',
    defaultUniverse: 'all',
    benchmark: 'BTC',
    benchmarkName: '比特币',
    currency: 'USDT',
    calendar: '24/7',
    adapterId: 'crypto',
  },
};

export function getMarketConfig(market: AppMarket): MarketConfig {
  return MARKET_CONFIGS[market] || MARKET_CONFIGS.CN;
}
