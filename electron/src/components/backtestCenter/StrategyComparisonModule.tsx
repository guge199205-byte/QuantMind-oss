/**
 * 策略对比模块（适配新布局）
 */

import React from 'react';
import { BacktestComparison } from '../backtest/BacktestComparison';
import { useBacktestCenterStore } from '../../stores/backtestCenterStore';
import { authService } from '../../features/auth/services/authService';

export const StrategyComparisonModule: React.FC = () => {
  const { backtestConfig, selectedBacktests } = useBacktestCenterStore();
  const storedUser = authService.getStoredUser() as
    | { id?: string | number; user_id?: string | number }
    | null;
  const resolvedUserId = storedUser?.id ?? storedUser?.user_id;
  const userId = String(resolvedUserId || backtestConfig.user_id || 'default');

  return (
    <div className="h-full p-6">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <BacktestComparison
          userId={userId}
          defaultBacktest1={selectedBacktests[0]}
          defaultBacktest2={selectedBacktests[1]}
        />
      </div>
    </div>
  );
};
