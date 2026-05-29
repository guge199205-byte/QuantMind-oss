/**
 * 交易记录存储服务
 */

import { StorageService } from './StorageService';
import { TradeRecord, OrderRecord, RangeQuery, QueryOptions } from './types';

export class TradeStorage extends StorageService {
  private static readonly TRADES_STORE = 'trades';
  private static readonly ORDERS_STORE = 'orders';

  constructor() {
    super({
      name: 'quantmind_trading_data',
      version: 1,
      stores: [
        {
          name: TradeStorage.TRADES_STORE,
          keyPath: 'id',
          autoIncrement: true,
          indexes: [
            { name: 'orderId', keyPath: 'orderId' },
            { name: 'symbol', keyPath: 'symbol' },
            { name: 'timestamp', keyPath: 'timestamp' },
            { name: 'symbol_timestamp', keyPath: ['symbol', 'timestamp'] },
          ],
        },
        {
          name: TradeStorage.ORDERS_STORE,
          keyPath: 'id',
          autoIncrement: true,
          indexes: [
            { name: 'orderId', keyPath: 'orderId', unique: true },
            { name: 'clientOrderId', keyPath: 'clientOrderId' },
            { name: 'symbol', keyPath: 'symbol' },
            { name: 'status', keyPath: 'status' },
            { name: 'timestamp', keyPath: 'timestamp' },
            { name: 'symbol_status', keyPath: ['symbol', 'status'] },
          ],
        },
      ],
    });
  }

  /**
   * 保存交易记录
   */
  async saveTrade(trade: Omit<TradeRecord, 'id' | 'createdAt'>): Promise<number> {
    const data: TradeRecord = {
      ...trade,
      createdAt: Date.now(),
    };

    const id = await this.add<TradeRecord>(TradeStorage.TRADES_STORE, data);
    return Number(id);
  }

  /**
   * 批量保存交易记录
   */
  async saveTradesBatch(trades: Omit<TradeRecord, 'id' | 'createdAt'>[]): Promise<number> {
    const dataArray = trades.map(trade => ({
      ...trade,
      createdAt: Date.now(),
    }));

    return this.addBatch<TradeRecord>(TradeStorage.TRADES_STORE, dataArray);
  }

  /**
   * 获取指定订单的交易记录
   */
  async getTradesByOrderId(orderId: string): Promise<TradeRecord[]> {
    return this.getByIndex<TradeRecord>(
      TradeStorage.TRADES_STORE,
      'orderId',
      orderId
    );
  }

  /**
   * 获取指定交易对的交易记录
   */
  async getTradesBySymbol(symbol: string, options?: QueryOptions): Promise<TradeRecord[]> {
    return this.getByIndex<TradeRecord>(
      TradeStorage.TRADES_STORE,
      'symbol',
      symbol,
      options
    );
  }

  /**
   * 获取时间范围内的交易记录
   */
  async getTradesByTimeRange(
    symbol: string,
    query: RangeQuery
  ): Promise<TradeRecord[]> {
    this.ensureDb();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(TradeStorage.TRADES_STORE, 'readonly');
      const store = transaction.objectStore(TradeStorage.TRADES_STORE);
      const index = store.index('symbol_timestamp');

      const range = IDBKeyRange.bound(
        [symbol, query.start],
        [symbol, query.end]
      );

      const request = index.getAll(range, query.limit);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 保存订单记录
   */
  async saveOrder(order: Omit<OrderRecord, 'id' | 'createdAt'>): Promise<number> {
    const data: OrderRecord = {
      ...order,
      createdAt: Date.now(),
    };

    try {
      const id = await this.add<OrderRecord>(TradeStorage.ORDERS_STORE, data);
      return Number(id);
    } catch (error: unknown) {
      // 如果是唯一性约束冲突，尝试更新
      const name = (error as { name?: string })?.name;
      if (name === 'ConstraintError') {
        return this.updateOrder(order);
      }
      throw error;
    }
  }

  /**
   * 更新订单记录
   */
  async updateOrder(order: Omit<OrderRecord, 'id' | 'createdAt'>): Promise<number> {
    const existing = await this.getByIndex<OrderRecord>(
      TradeStorage.ORDERS_STORE,
      'orderId',
      order.orderId
    );

    if (existing.length > 0) {
      const updated = {
        ...existing[0],
        ...order,
      };
      const id = await this.update<OrderRecord>(TradeStorage.ORDERS_STORE, updated);
      return Number(id);
    }

    throw new Error('未找到要更新的订单记录');
  }

  /**
   * 获取订单记录
   */
  async getOrderById(orderId: string): Promise<OrderRecord | undefined> {
    const orders = await this.getByIndex<OrderRecord>(
      TradeStorage.ORDERS_STORE,
      'orderId',
      orderId
    );
    return orders[0];
  }

  /**
   * 获取指定交易对的订单
   */
  async getOrdersBySymbol(symbol: string, options?: QueryOptions): Promise<OrderRecord[]> {
    return this.getByIndex<OrderRecord>(
      TradeStorage.ORDERS_STORE,
      'symbol',
      symbol,
      options
    );
  }

  /**
   * 获取指定状态的订单
   */
  async getOrdersByStatus(status: string, options?: QueryOptions): Promise<OrderRecord[]> {
    return this.getByIndex<OrderRecord>(
      TradeStorage.ORDERS_STORE,
      'status',
      status,
      options
    );
  }

  /**
   * 获取活跃订单（未完成）
   */
  async getActiveOrders(symbol?: string): Promise<OrderRecord[]> {
    const activeStatuses = ['NEW', 'PARTIALLY_FILLED', 'PENDING'];
    const allOrders: OrderRecord[] = [];

    for (const status of activeStatuses) {
      if (symbol) {
        const orders = await this.getByIndex<OrderRecord>(
          TradeStorage.ORDERS_STORE,
          'symbol_status',
          [symbol, status]
        );
        allOrders.push(...orders);
      } else {
        const orders = await this.getOrdersByStatus(status);
        allOrders.push(...orders);
      }
    }

    return allOrders;
  }

  /**
   * 获取交易统计
   */
  async getTradeStats(symbol?: string): Promise<{
    totalTrades: number;
    totalVolume: number;
    totalQuoteVolume: number;
    totalCommission: number;
    avgPrice: number;
  }> {
    let trades: TradeRecord[];

    if (symbol) {
      trades = await this.getTradesBySymbol(symbol);
    } else {
      trades = await this.getAll<TradeRecord>(TradeStorage.TRADES_STORE);
    }

    const stats = trades.reduce((acc, trade) => {
      return {
        totalVolume: acc.totalVolume + trade.quantity,
        totalQuoteVolume: acc.totalQuoteVolume + trade.quoteQuantity,
        totalCommission: acc.totalCommission + trade.commission,
      };
    }, { totalVolume: 0, totalQuoteVolume: 0, totalCommission: 0 });

    return {
      totalTrades: trades.length,
      ...stats,
      avgPrice: stats.totalQuoteVolume / stats.totalVolume || 0,
    };
  }

  /**
   * 删除过期的交易记录
   */
  async deleteExpiredTrades(beforeTimestamp: number): Promise<number> {
    const trades = await this.getAll<TradeRecord>(TradeStorage.TRADES_STORE);
    let deletedCount = 0;

    for (const trade of trades) {
      if (trade.timestamp < beforeTimestamp && trade.id) {
        await this.delete(TradeStorage.TRADES_STORE, trade.id);
        deletedCount++;
      }
    }

    return deletedCount;
  }

  /**
   * 删除过期的订单记录
   */
  async deleteExpiredOrders(beforeTimestamp: number): Promise<number> {
    const orders = await this.getAll<OrderRecord>(TradeStorage.ORDERS_STORE);
    let deletedCount = 0;

    for (const order of orders) {
      if (order.timestamp < beforeTimestamp && order.id) {
        await this.delete(TradeStorage.ORDERS_STORE, order.id);
        deletedCount++;
      }
    }

    return deletedCount;
  }

  /**
   * 确保数据库已初始化
   */

}
