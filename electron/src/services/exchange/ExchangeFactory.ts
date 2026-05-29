/**
 * 交易所工厂
 */

import { BaseRestClient } from './base/BaseRestClient';
import { BinanceAPI } from './binance/BinanceAPI';

export type ExchangeType = 'binance' | 'huobi' | 'okex' | 'coinbase';

export interface ExchangeConfig {
  apiKey: string;
  apiSecret: string;
  passphrase?: string;
  sandbox?: boolean;
  timeout?: number;
}

export class ExchangeFactory {
  /**
   * 创建交易所API实例
   */
  static createExchange(type: ExchangeType, config: ExchangeConfig): BaseRestClient {
    switch (type) {
      case 'binance':
        return new BinanceAPI(config);
      case 'huobi':
        throw new Error('Huobi API not implemented yet');
      case 'okex':
        throw new Error('OKEx API not implemented yet');
      case 'coinbase':
        throw new Error('Coinbase API not implemented yet');
      default:
        throw new Error(`Unsupported exchange type: ${type}`);
    }
  }

  /**
   * 获取支持的交易所列表
   */
  static getSupportedExchanges(): ExchangeType[] {
    return ['binance', 'huobi', 'okex', 'coinbase'];
  }

  /**
   * 兼容旧API：create 别名
   */
  static create(type: ExchangeType, config: ExchangeConfig): BaseRestClient {
    return ExchangeFactory.createExchange(type, config);
  }
}
