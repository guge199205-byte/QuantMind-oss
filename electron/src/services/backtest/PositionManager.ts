/**
 * 仓位管理器
 * 管理持仓、保证金和风险控制
 */

import { Position, Trade, OrderExecution } from '../../types/backtest';

export class PositionManager {
  private position: Position | null = null;
  private capital: number;
  private initialCapital: number;
  private leverage: number;
  private riskPerTrade: number;
  private trades: Trade[] = [];

  constructor(
    initialCapital: number,
    leverage: number = 1,
    riskPerTrade: number = 0.02
  ) {
    this.capital = initialCapital;
    this.initialCapital = initialCapital;
    this.leverage = leverage;
    this.riskPerTrade = riskPerTrade;
  }

  /**
   * 开仓
   */
  openPosition(
    symbol: string,
    side: 'buy' | 'sell',
    size: number,
    execution: OrderExecution
  ): Trade | null {
    // 检查是否有足够资金
    const requiredCapital = (execution.executionPrice * size) / this.leverage;
    const totalCost = requiredCapital + execution.commission;

    if (totalCost > this.capital) {
      console.warn('Insufficient capital to open position');
      return null;
    }

    // 如果已有持仓，先平仓
    if (this.position) {
      this.closePosition(execution.executionPrice, execution.timestamp);
    }

    // 创建新持仓
    this.position = {
      symbol,
      size: side === 'buy' ? size : -size,
      entryPrice: execution.executionPrice,
      currentPrice: execution.executionPrice,
      unrealizedPnL: 0,
      realizedPnL: 0
    };

    // 扣除资金
    this.capital -= totalCost;

    // 记录交易
    const trade: Trade = {
      id: execution.orderId,
      timestamp: execution.timestamp,
      symbol,
      side,
      price: execution.executionPrice,
      size,
      commission: execution.commission,
      slippage: execution.slippage
    };

    this.trades.push(trade);
    return trade;
  }

  /**
   * 平仓
   */
  closePosition(currentPrice: number, timestamp: number): Trade | null {
    if (!this.position) {
      return null;
    }

    const size = Math.abs(this.position.size);
    const side: 'buy' | 'sell' = this.position.size > 0 ? 'sell' : 'buy';

    // 计算盈亏
    const pnl = this.calculatePnL(currentPrice);

    // 归还资金
    const positionValue = currentPrice * size;
    this.capital += positionValue + pnl;

    // 记录平仓交易
    const trade: Trade = {
      id: `CLOSE_${timestamp}`,
      timestamp,
      symbol: this.position.symbol,
      side,
      price: currentPrice,
      size,
      commission: 0,
      slippage: 0,
      pnl,
      cumulativePnL: this.getTotalPnL()
    };

    this.trades.push(trade);
    this.position = null;

    return trade;
  }

  /**
   * 更新持仓当前价格
   */
  updatePosition(currentPrice: number): void {
    if (this.position) {
      this.position.currentPrice = currentPrice;
      this.position.unrealizedPnL = this.calculatePnL(currentPrice);
    }
  }

  /**
   * 计算未实现盈亏
   */
  private calculatePnL(currentPrice: number): number {
    if (!this.position) return 0;

    const priceDiff = currentPrice - this.position.entryPrice;
    const pnl = priceDiff * this.position.size;

    return pnl;
  }

  /**
   * 获取当前权益
   */
  getEquity(): number {
    let equity = this.capital;

    if (this.position) {
      equity += this.position.currentPrice * Math.abs(this.position.size);
      equity += this.position.unrealizedPnL;
    }

    return equity;
  }

  /**
   * 获取当前持仓
   */
  getPosition(): Position | null {
    return this.position;
  }

  /**
   * 获取当前资金
   */
  getCapital(): number {
    return this.capital;
  }

  /**
   * 获取所有交易记录
   */
  getTrades(): Trade[] {
    return this.trades;
  }

  /**
   * 计算总盈亏
   */
  getTotalPnL(): number {
    return this.trades
      .filter(t => t.pnl !== undefined)
      .reduce((sum, t) => sum + (t.pnl || 0), 0);
  }

  /**
   * 计算持仓占用保证金
   */
  getUsedMargin(): number {
    if (!this.position) return 0;

    return (this.position.currentPrice * Math.abs(this.position.size)) / this.leverage;
  }

  /**
   * 计算可用保证金
   */
  getAvailableMargin(): number {
    return this.capital - this.getUsedMargin();
  }

  /**
   * 根据风险计算仓位大小
   */
  calculatePositionSize(
    entryPrice: number,
    stopLoss: number,
    riskAmount?: number
  ): number {
    const risk = riskAmount || this.capital * this.riskPerTrade;
    const priceRisk = Math.abs(entryPrice - stopLoss);

    if (priceRisk === 0) return 0;

    const size = risk / priceRisk;

    // 考虑杠杆
    const maxSize = (this.capital * this.leverage) / entryPrice;

    return Math.min(size, maxSize);
  }

  /**
   * 重置管理器
   */
  reset(): void {
    this.position = null;
    this.capital = this.initialCapital;
    this.trades = [];
  }

  /**
   * 获取统计信息
   */
  getStatistics() {
    const totalTrades = this.trades.filter(t => t.pnl !== undefined).length;
    const winningTrades = this.trades.filter(t => t.pnl && t.pnl > 0).length;
    const losingTrades = this.trades.filter(t => t.pnl && t.pnl < 0).length;

    const totalPnL = this.getTotalPnL();
    const totalCommission = this.trades.reduce((sum, t) => sum + t.commission, 0);
    const totalSlippage = this.trades.reduce((sum, t) => sum + t.slippage, 0);

    const wins = this.trades.filter(t => t.pnl && t.pnl > 0).map(t => t.pnl!);
    const losses = this.trades.filter(t => t.pnl && t.pnl < 0).map(t => t.pnl!);

    const averageWin = wins.length > 0
      ? wins.reduce((a, b) => a + b, 0) / wins.length
      : 0;

    const averageLoss = losses.length > 0
      ? losses.reduce((a, b) => a + b, 0) / losses.length
      : 0;

    return {
      totalTrades,
      winningTrades,
      losingTrades,
      winRate: totalTrades > 0 ? winningTrades / totalTrades : 0,
      totalPnL,
      totalCommission,
      totalSlippage,
      averageWin,
      averageLoss,
      profitFactor: Math.abs(averageLoss) > 0 ? averageWin / Math.abs(averageLoss) : 0,
      currentEquity: this.getEquity(),
      returnRate: (this.getEquity() - this.initialCapital) / this.initialCapital
    };
  }
}
