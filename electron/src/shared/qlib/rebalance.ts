export type RebalanceDays = 1 | 3 | 5;

export const QLIB_REBALANCE_DAY_OPTIONS: Array<{ value: RebalanceDays; label: string; labelEn: string }> = [
  { value: 1, label: '每1天', labelEn: '1 Day' },
  { value: 3, label: '每3天', labelEn: '3 Days' },
  { value: 5, label: '每5天', labelEn: '5 Days' },
];

export const QLIB_REBALANCE_DAY_LABEL: Record<RebalanceDays, string> = {
  1: '每1天',
  3: '每3天',
  5: '每5天',
};

export const resolveRebalanceDays = (params?: { rebalance_days?: number; rebalance_period?: string }): RebalanceDays => {
  if (params?.rebalance_days === 1 || params?.rebalance_days === 3 || params?.rebalance_days === 5) {
    return params.rebalance_days;
  }
  if (params?.rebalance_period === 'daily') return 1;
  return 5;
};

