/**
 * 订单模拟器
 * 模拟订单执行，包括滑点和手续费
 */

import { OHLCV, OrderRequest, OrderExecution } from '../../types/backtest';

export class OrderSimulator {
  private commission: number;
  private slippage: number;
  private orderId: number = 0;

  constructor(commission: number = 0.001, slippage: number = 0.001) {
    this.commission = commission;
    this.slippage = slippage;
  }

  /**
   * 模拟市价单执行
   */
  simulateMarketOrder(
    order: OrderRequest,
    bar: OHLCV,
    timestamp: number
  ): OrderExecution {
    if (order.type !== 'market') {
      throw new Error('This method only handles market orders');
    }

    // 市价单使用下一根K线的开盘价（模拟真实场景）
    let executionPrice = bar.open;

    // 应用滑点
    if (order.side === 'buy') {
      executionPrice *= (1 + this.slippage);
    } else {
      executionPrice *= (1 - this.slippage);
    }

    // 计算手续费
    const commission = executionPrice * order.size * this.commission;

    // 计算实际滑点金额
    const slippageAmount = Math.abs(executionPrice - bar.open) * order.size;

    return {
      orderId: this.generateOrderId(),
      executionPrice,
      executionSize: order.size,
      commission,
      slippage: slippageAmount,
      timestamp
    };
  }

  /**
   * 模拟限价单执行
   */
  simulateLimitOrder(
    order: OrderRequest,
    bar: OHLCV,
    timestamp: number
  ): OrderExecution | null {
    if (order.type !== 'limit' || !order.price) {
      throw new Error('This method only handles limit orders with price');
    }

    // 检查限价单是否能成交
    const canExecute = this.canLimitOrderExecute(order, bar);

    if (!canExecute) {
      return null;
    }

    // 限价单以指定价格成交
    const executionPrice = order.price;
    const commission = executionPrice * order.size * this.commission;

    return {
      orderId: this.generateOrderId(),
      executionPrice,
      executionSize: order.size,
      commission,
      slippage: 0, // 限价单无滑点
      timestamp
    };
  }

  /**
   * 模拟止损单执行
   */
  simulateStopOrder(
    order: OrderRequest,
    bar: OHLCV,
    timestamp: number
  ): OrderExecution | null {
    if (order.type !== 'stop' || !order.stopPrice) {
      throw new Error('This method only handles stop orders with stop price');
    }

    // 检查止损单是否触发
    const triggered = this.isStopOrderTriggered(order, bar);

    if (!triggered) {
      return null;
    }

    // 止损单触发后以市价成交
    let executionPrice = order.stopPrice;

    // 止损单通常会有较大滑点
    const stopSlippage = this.slippage * 2;
    if (order.side === 'buy') {
      executionPrice *= (1 + stopSlippage);
    } else {
      executionPrice *= (1 - stopSlippage);
    }

    const commission = executionPrice * order.size * this.commission;
    const slippageAmount = Math.abs(executionPrice - order.stopPrice) * order.size;

    return {
      orderId: this.generateOrderId(),
      executionPrice,
      executionSize: order.size,
      commission,
      slippage: slippageAmount,
      timestamp
    };
  }

  /**
   * 检查限价单是否能成交
   */
  private canLimitOrderExecute(order: OrderRequest, bar: OHLCV): boolean {
    if (!order.price) return false;

    if (order.side === 'buy') {
      // 买入限价单：如果最低价低于限价，则成交
      return bar.low <= order.price;
    } else {
      // 卖出限价单：如果最高价高于限价，则成交
      return bar.high >= order.price;
    }
  }

  /**
   * 检查止损单是否触发
   */
  private isStopOrderTriggered(order: OrderRequest, bar: OHLCV): boolean {
    if (!order.stopPrice) return false;

    if (order.side === 'buy') {
      // 买入止损：价格向上突破止损价
      return bar.high >= order.stopPrice;
    } else {
      // 卖出止损：价格向下突破止损价
      return bar.low <= order.stopPrice;
    }
  }

  /**
   * 生成订单ID
   */
  private generateOrderId(): string {
    return `ORDER_${++this.orderId}_${Date.now()}`;
  }

  /**
   * 设置手续费率
   */
  setCommission(commission: number): void {
    this.commission = commission;
  }

  /**
   * 设置滑点
   */
  setSlippage(slippage: number): void {
    this.slippage = slippage;
  }

  /**
   * 获取当前手续费率
   */
  getCommission(): number {
    return this.commission;
  }

  /**
   * 获取当前滑点
   */
  getSlippage(): number {
    return this.slippage;
  }
}
