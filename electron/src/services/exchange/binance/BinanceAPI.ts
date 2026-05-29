/**
 * Binance API客户端
 */

import { AxiosRequestConfig } from 'axios';
import { BaseRestClient, RequestOptions } from '../base/BaseRestClient';
import { RateLimiter } from '../base/RateLimiter';
import { Signature } from '../../../utils/crypto/Signature';
import type {
  ExchangeConfig,
  Kline,
  OrderBook,
  Trade,
  Ticker24h,
  Balance,
  Order,
  CreateOrderParams,
  ApiResponse
} from '../base/types';

export class BinanceAPI extends BaseRestClient {
  private rateLimiter: RateLimiter;
  private recvWindow: number = 5000;

  constructor(config: ExchangeConfig) {
    const baseURL = config.testnet
      ? 'https://testnet.binance.vision/api'
      : 'https://api.binance.com/api';

    super(config, baseURL);

    // Binance速率限制：1200请求/分钟 = 20请求/秒
    this.rateLimiter = new RateLimiter({
      maxTokens: 20,
      minInterval: 50 // 50ms最小间隔
    });
  }

  /**
   * 签名请求
   */
  protected async signRequest(
    config: AxiosRequestConfig,
    options: RequestOptions
  ): Promise<void> {
    const timestamp = Signature.timestamp();
    const params = {
      ...(options.params || {}),
      timestamp,
      recvWindow: this.recvWindow
    };

    const queryString = Signature.buildQueryString(params);
    const signature = Signature.hmacSha256(queryString, this.config.apiSecret);

    config.params = {
      ...params,
      signature
    };

    config.headers = {
      ...config.headers,
      'X-MBX-APIKEY': this.config.apiKey
    };
  }

  /**
   * ===== 市场数据API =====
   */

  /**
   * 获取K线数据
   */
  async getKlines(
    symbol: string,
    interval: string,
    limit: number = 500,
    startTime?: number,
    endTime?: number
  ): Promise<ApiResponse<Kline[]>> {
    await this.rateLimiter.acquire();

    const params: Record<string, unknown> = {
      symbol,
      interval,
      limit
    };

    if (startTime) (params as Record<string, unknown>).startTime = startTime;
    if (endTime) (params as Record<string, unknown>).endTime = endTime;

    const response = await this.get<unknown[]>('/v3/klines', params);

    if (response.success && response.data) {
      const klines: Kline[] = response.data.map(k => {
        const arr = k as unknown as Array<unknown>;
        return {
          timestamp: Number(arr[0]) as number,
          open: parseFloat(String(arr[1] ?? '0')),
          high: parseFloat(String(arr[2] ?? '0')),
          low: parseFloat(String(arr[3] ?? '0')),
          close: parseFloat(String(arr[4] ?? '0')),
          volume: parseFloat(String(arr[5] ?? '0'))
        };
      });

      return { success: true, data: klines };
    }

    return response as ApiResponse<Kline[]>;
  }

  /**
   * 获取24小时行情
   */
  async getTicker24h(symbol?: string): Promise<ApiResponse<Ticker24h | Ticker24h[]>> {
    await this.rateLimiter.acquire();

    const params = symbol ? { symbol } : undefined;
    const response = await this.get<unknown>('/v3/ticker/24hr', params);

    if (response.success && response.data) {
      const transform = (data: unknown): Ticker24h => {
        const d = data as Record<string, unknown>;
        return {
          symbol: String(d.symbol ?? ''),
          priceChange: parseFloat(String(d.priceChange ?? '0')),
          priceChangePercent: parseFloat(String(d.priceChangePercent ?? '0')),
          lastPrice: parseFloat(String(d.lastPrice ?? '0')),
          highPrice: parseFloat(String(d.highPrice ?? '0')),
          lowPrice: parseFloat(String(d.lowPrice ?? '0')),
          volume: parseFloat(String(d.volume ?? '0')),
          quoteVolume: parseFloat(String(d.quoteVolume ?? '0'))
        };
      };

      const ticker = Array.isArray(response.data)
        ? (response.data as unknown[]).map(transform)
        : transform(response.data as unknown);

      return { success: true, data: ticker };
    }

    return response as ApiResponse<Ticker24h | Ticker24h[]>;
  }

  /**
   * 获取订单簿
   */
  async getOrderBook(symbol: string, limit: number = 100): Promise<ApiResponse<OrderBook>> {
    await this.rateLimiter.acquire();

    const response = await this.get<unknown>('/v3/depth', { symbol, limit });

    if (response.success && response.data) {
      const data = response.data as Record<string, unknown>;
      const bids = (data.bids as unknown[] | undefined) ?? [];
      const asks = (data.asks as unknown[] | undefined) ?? [];

      const orderBook: OrderBook = {
        timestamp: Date.now(),
        bids: bids.map(b => {
          const arr = b as unknown as Array<unknown>;
          return [parseFloat(String(arr[0] ?? '0')), parseFloat(String(arr[1] ?? '0'))] as [number, number];
        }),
        asks: asks.map(a => {
          const arr = a as unknown as Array<unknown>;
          return [parseFloat(String(arr[0] ?? '0')), parseFloat(String(arr[1] ?? '0'))] as [number, number];
        })
      };

      return { success: true, data: orderBook };
    }

    return response as ApiResponse<OrderBook>;
  }

  /**
   * 获取最近成交
   */
  async getTrades(symbol: string, limit: number = 500): Promise<ApiResponse<Trade[]>> {
    await this.rateLimiter.acquire();

    const response = await this.get<unknown[]>('/v3/trades', { symbol, limit });

    if (response.success && response.data) {
      const trades: Trade[] = (response.data as unknown[]).map(t => {
        const r = t as Record<string, unknown>;
        return {
          id: String(r.id ?? ''),
          timestamp: Number(r.time ?? Date.now()),
          price: parseFloat(String(r.price ?? '0')),
          quantity: parseFloat(String(r.qty ?? '0')),
          side: (r.isBuyerMaker ? 'sell' : 'buy') as 'sell' | 'buy'
        } as Trade;
      });

      return { success: true, data: trades };
    }

    return response as ApiResponse<Trade[]>;
  }

  /**
   * ===== 账户和交易API =====
   */

  /**
   * 获取账户余额
   */
  async getBalances(): Promise<ApiResponse<Balance[]>> {
    await this.rateLimiter.acquire();

    const response = await this.get<unknown>('/v3/account', undefined, true);

    if (response.success && response.data) {
      const data = response.data as Record<string, unknown>;
      const balancesArr = (data.balances as unknown[] | undefined) ?? [];

      const balances: Balance[] = balancesArr
        .map(b => b as Record<string, unknown>)
        .filter(b => parseFloat(String(b.free ?? '0')) > 0 || parseFloat(String(b.locked ?? '0')) > 0)
        .map(b => ({
          asset: String(b.asset ?? ''),
          free: parseFloat(String(b.free ?? '0')),
          locked: parseFloat(String(b.locked ?? '0')),
          total: parseFloat(String(b.free ?? '0')) + parseFloat(String(b.locked ?? '0'))
        }));

      return { success: true, data: balances };
    }

    return response as ApiResponse<Balance[]>;
  }

  /**
   * 创建订单
   */
  async createOrder(params: CreateOrderParams): Promise<ApiResponse<Order>> {
    await this.rateLimiter.acquire();

    const orderParams: Record<string, unknown> = {
      symbol: params.symbol,
      side: params.side,
      type: params.type,
      quantity: params.quantity
    };

    if (params.type === 'LIMIT') {
      (orderParams as Record<string, unknown>).price = params.price;
      (orderParams as Record<string, unknown>).timeInForce = params.timeInForce || 'GTC';
    }

    if (params.clientOrderId) {
      (orderParams as Record<string, unknown>).newClientOrderId = params.clientOrderId;
    }

    const response = await this.post<unknown>('/v3/order', orderParams, true);

    if (response.success && response.data) {
      const d = response.data as Record<string, unknown>;
      const order: Order = {
        orderId: String(d.orderId ?? ''),
        clientOrderId: d.clientOrderId as string | undefined,
        symbol: String(d.symbol ?? ''),
        side: d.side as Order['side'],
        type: d.type as Order['type'],
        price: parseFloat(String(d.price ?? '0')),
        quantity: parseFloat(String(d.origQty ?? '0')),
        executedQty: parseFloat(String(d.executedQty ?? '0')),
        status: String(d.status ?? '') as Order['status'],
        timestamp: Number(d.transactTime ?? Date.now())
      };

      return { success: true, data: order };
    }

    return response as ApiResponse<Order>;
  }

  /**
   * 取消订单
   */
  async cancelOrder(symbol: string, orderId: string): Promise<ApiResponse<Order>> {
    await this.rateLimiter.acquire();

    const response = await this.delete<unknown>(
      '/v3/order',
      { symbol, orderId },
      true
    );

    if (response.success && response.data) {
      const d = response.data as Record<string, unknown>;
      const order: Order = {
        orderId: String(d.orderId ?? ''),
        clientOrderId: d.clientOrderId as string | undefined,
        symbol: String(d.symbol ?? ''),
        side: d.side as Order['side'],
        type: d.type as Order['type'],
        quantity: parseFloat(String(d.origQty ?? '0')),
        executedQty: parseFloat(String(d.executedQty ?? '0')),
        status: String(d.status ?? '') as Order['status'],
        timestamp: Date.now()
      };

      return { success: true, data: order };
    }

    return response as ApiResponse<Order>;
  }

  /**
   * 查询订单
   */
  async getOrder(symbol: string, orderId: string): Promise<ApiResponse<Order>> {
    await this.rateLimiter.acquire();

    const response = await this.get<unknown>(
      '/v3/order',
      { symbol, orderId },
      true
    );

    if (response.success && response.data) {
      const d = response.data as Record<string, unknown>;
      const order: Order = {
        orderId: String(d.orderId ?? ''),
        clientOrderId: d.clientOrderId as string | undefined,
        symbol: String(d.symbol ?? ''),
        side: d.side as Order['side'],
        type: d.type as Order['type'],
        price: parseFloat(String(d.price ?? '0')),
        quantity: parseFloat(String(d.origQty ?? '0')),
        executedQty: parseFloat(String(d.executedQty ?? '0')),
        status: String(d.status ?? '') as Order['status'],
        timestamp: Number(d.time ?? Date.now()),
        updateTime: Number(d.updateTime ?? 0)
      };

      return { success: true, data: order };
    }

    return response as ApiResponse<Order>;
  }

  /**
   * 获取当前活跃订单
   */
  async getOpenOrders(symbol?: string): Promise<ApiResponse<Order[]>> {
    await this.rateLimiter.acquire();

    const params = symbol ? { symbol } : undefined;
    const response = await this.get<unknown[]>('/v3/openOrders', params, true);

    if (response.success && response.data) {
      const orders: Order[] = (response.data as unknown[]).map(o => {
        const d = o as Record<string, unknown>;
        return {
          orderId: String(d.orderId ?? ''),
          clientOrderId: d.clientOrderId as string | undefined,
          symbol: String(d.symbol ?? ''),
          side: d.side as Order['side'],
          type: d.type as Order['type'],
          price: parseFloat(String(d.price ?? '0')),
          quantity: parseFloat(String(d.origQty ?? '0')),
          executedQty: parseFloat(String(d.executedQty ?? '0')),
          status: String(d.status ?? '') as Order['status'],
          timestamp: Number(d.time ?? Date.now()),
          updateTime: Number(d.updateTime ?? 0)
        } as Order;
      });

      return { success: true, data: orders };
    }

    return response as ApiResponse<Order[]>;
  }
}
