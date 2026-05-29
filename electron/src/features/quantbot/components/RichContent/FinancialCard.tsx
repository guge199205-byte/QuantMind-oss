/**
 * 财报卡片组件 - 以卡片形式展示财务数据
 */

import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, DollarSign, Activity } from 'lucide-react';

export interface FinancialMetric {
  label: string;
  value: number | string;
  unit?: string;
  change?: number;
  changeType?: 'increase' | 'decrease';
  highlight?: boolean;
}

export interface FinancialCardProps {
  title: string;
  subtitle?: string;
  metrics: FinancialMetric[];
  period?: string;
  companyName?: string;
  tsCode?: string;
}

const FinancialCard: React.FC<FinancialCardProps> = ({
  title,
  subtitle,
  metrics,
  period,
  companyName,
  tsCode,
}) => {
  const formatValue = (value: number | string, unit?: string): string => {
    if (typeof value === 'number') {
      // 格式化数字，添加千位分隔符
      const formatted = value.toLocaleString('zh-CN', {
        maximumFractionDigits: 2,
      });
      return unit ? `${formatted}${unit}` : formatted;
    }
    return unit ? `${value}${unit}` : value.toString();
  };

  const formatChange = (change: number): string => {
    const sign = change > 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}%`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden"
    >
      {/* 卡片头部 */}
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-4 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold">{title}</h3>
            {subtitle && (
              <p className="text-sm text-blue-100 mt-1">{subtitle}</p>
            )}
          </div>
          <DollarSign className="w-8 h-8 opacity-80" />
        </div>

        {/* 公司信息 */}
        {(companyName || tsCode) && (
          <div className="mt-2 flex items-center gap-2 text-sm">
            {companyName && <span className="font-medium">{companyName}</span>}
            {tsCode && (
              <span className="px-2 py-0.5 bg-white/20 rounded text-xs">
                {tsCode}
              </span>
            )}
            {period && (
              <span className="ml-auto text-xs text-blue-100">{period}</span>
            )}
          </div>
        )}
      </div>

      {/* 指标列表 */}
      <div className="p-4 space-y-3">
        {metrics.map((metric, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
            className={`flex items-center justify-between p-3 rounded-lg ${
              metric.highlight
                ? 'bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200'
                : 'bg-gray-50'
            }`}
          >
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-medium text-gray-700">
                {metric.label}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className={`text-base font-bold ${
                metric.highlight ? 'text-blue-600' : 'text-gray-900'
              }`}>
                {formatValue(metric.value, metric.unit)}
              </span>

              {metric.change !== undefined && (
                <div className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded ${
                  metric.changeType === 'increase'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700'
                }`}>
                  {metric.changeType === 'increase' ? (
                    <TrendingUp className="w-3 h-3" />
                  ) : (
                    <TrendingDown className="w-3 h-3" />
                  )}
                  <span>{formatChange(metric.change)}</span>
                </div>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
};

export default FinancialCard;
