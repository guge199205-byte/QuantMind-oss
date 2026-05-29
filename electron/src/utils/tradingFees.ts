/**
 * A股交易费用计算工具
 * 基于 docs/费用.md 的真实费用结构
 */

/**
 * A股交易费用常量
 * 参考: docs/费用.md
 */
export const TRADING_FEES = {
  // 券商佣金（买卖双向）
  COMMISSION_RATE: 0.00025,      // 万2.5
  MIN_COMMISSION: 5,             // 最低5元

  // 过户费（买卖双向，仅沪市，已并入全市场）
  TRANSFER_FEE_RATE: 0.00001,    // 万0.1

  // 印花税（仅卖出）
  STAMP_TAX_RATE: 0.0005,        // 万5 (2023年8月28日起从千分之一减半)

  // 综合费率
  BUY_COST_RATE: 0.00026,        // 买入总费用 = 佣金 + 过户费
  SELL_COST_RATE: 0.00076,       // 卖出总费用 = 佣金 + 过户费 + 印花税
} as const;

/**
 * 交易费用明细
 */
export interface TradingFeeBreakdown {
  commission: number;      // 佣金
  transferFee: number;     // 过户费
  stampTax: number;        // 印花税（仅卖出）
  total: number;           // 总费用
}

/**
 * 计算买入费用
 * @param amount 交易金额（元）
 * @param commissionRate 佣金费率（默认万2.5）
 * @returns 费用明细
 */
export function calculateBuyFee(
  amount: number,
  commissionRate: number = TRADING_FEES.COMMISSION_RATE
): TradingFeeBreakdown {
  // 佣金（最低5元）
  const commission = Math.max(
    amount * commissionRate,
    TRADING_FEES.MIN_COMMISSION
  );

  // 过户费
  const transferFee = amount * TRADING_FEES.TRANSFER_FEE_RATE;

  // 买入无印花税
  const stampTax = 0;

  const total = commission + transferFee + stampTax;

  return {
    commission,
    transferFee,
    stampTax,
    total,
  };
}

/**
 * 计算卖出费用
 * @param amount 交易金额（元）
 * @param commissionRate 佣金费率（默认万2.5）
 * @returns 费用明细
 */
export function calculateSellFee(
  amount: number,
  commissionRate: number = TRADING_FEES.COMMISSION_RATE
): TradingFeeBreakdown {
  // 佣金（最低5元）
  const commission = Math.max(
    amount * commissionRate,
    TRADING_FEES.MIN_COMMISSION
  );

  // 过户费
  const transferFee = amount * TRADING_FEES.TRANSFER_FEE_RATE;

  // 印花税（仅卖出）
  const stampTax = amount * TRADING_FEES.STAMP_TAX_RATE;

  const total = commission + transferFee + stampTax;

  return {
    commission,
    transferFee,
    stampTax,
    total,
  };
}

/**
 * 计算完整交易（买入+卖出）的总费用
 * @param amount 交易金额（元）
 * @param commissionRate 佣金费率（默认万2.5）
 * @returns 买入、卖出和总费用明细
 */
export function calculateRoundTripFee(
  amount: number,
  commissionRate: number = TRADING_FEES.COMMISSION_RATE
) {
  const buyFee = calculateBuyFee(amount, commissionRate);
  const sellFee = calculateSellFee(amount, commissionRate);

  return {
    buy: buyFee,
    sell: sellFee,
    total: buyFee.total + sellFee.total,
    totalRate: (buyFee.total + sellFee.total) / amount,
  };
}

/**
 * 格式化费用为易读字符串
 */
export function formatFee(fee: TradingFeeBreakdown): string {
  const parts: string[] = [];

  if (fee.commission > 0) {
    parts.push(`佣金: ${fee.commission.toFixed(2)}元`);
  }

  if (fee.transferFee > 0) {
    parts.push(`过户费: ${fee.transferFee.toFixed(2)}元`);
  }

  if (fee.stampTax > 0) {
    parts.push(`印花税: ${fee.stampTax.toFixed(2)}元`);
  }

  parts.push(`合计: ${fee.total.toFixed(2)}元`);

  return parts.join(', ');
}

/**
 * 计算费用示例（用于文档和UI展示）
 */
export const FEE_EXAMPLES = {
  // 10万元交易示例
  amount_100k: {
    amount: 100000,
    buy: calculateBuyFee(100000),
    sell: calculateSellFee(100000),
    roundTrip: calculateRoundTripFee(100000),
  },

  // 1万元交易示例（会触发最低佣金5元）
  amount_10k: {
    amount: 10000,
    buy: calculateBuyFee(10000),
    sell: calculateSellFee(10000),
    roundTrip: calculateRoundTripFee(10000),
  },

  // 小额交易（佣金不足5元）
  amount_1k: {
    amount: 1000,
    buy: calculateBuyFee(1000),
    sell: calculateSellFee(1000),
    roundTrip: calculateRoundTripFee(1000),
  },
} as const;
