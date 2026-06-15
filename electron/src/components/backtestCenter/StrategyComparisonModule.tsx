/**
 * 策略对比模块（适配新布局）
 */

import React from 'react';
import { motion } from 'framer-motion';
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
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6"
      >
        <BacktestComparison
          userId={userId}
          defaultBacktest1={selectedBacktests[0]}
          defaultBacktest2={selectedBacktests[1]}
        />
      </motion.div>
    </div>
  );
};
