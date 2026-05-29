/**
 * 快速回测模块
 *
 * 注意：已重构为使用 QlibQuickBacktest 组件
 */

import React from 'react';
import { QlibQuickBacktest as QlibQuickBacktestComponent } from '../backtest/QlibQuickBacktest';

export const QuickBacktest: React.FC = () => {
  return <QlibQuickBacktestComponent />;
};
