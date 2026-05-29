import React from 'react';
import { Card } from '../common/Card';
import { MarketOverviewSkeleton } from '../common/CardSkeletons';
import { useMarketData } from '../../hooks/useMarketData';
import { MarketIndex } from '../../services/marketService';

export const MarketOverviewCard: React.FC = () => {
  const { data, loading, error } = useMarketData();

  // 默认数据，以防API调用失败
  const marketData: Partial<MarketIndex>[] = [
    { name: '上证指数', price: 3882.78, change: 20.12, changePercent: 0.52 },
    { name: '深成指数', price: 13526.51, change: 47.23, changePercent: 0.35 },
    { name: '创业板指', price: 3238.16, change: -15.84, changePercent: -0.49 },
    { name: '沪深300', price: 4640.69, change: 20.78, changePercent: 0.45 },
    { name: '中证500', price: 6789.34, change: -12.56, changePercent: -0.18 },
    { name: '上证50', price: 3456.89, change: 15.23, changePercent: 0.44 }
  ];

  if (loading) {
    return <MarketOverviewSkeleton />;
  }

  if (error) {
    console.error('获取市场数据出错:', error);
  }

  const displayData = data?.indices || marketData;

  return (
    <Card title="大盘概览" height="100%" background="market">
      <div className="flex flex-col justify-between h-full py-2">
        {/* 市场数据项 - 优化布局 */}
        {displayData.slice(0, 6).map((item, index) => (
          <div
            key={index}
            className="
              flex items-center justify-between px-3 py-3 rounded-lg
              bg-slate-50 border border-slate-100/80
              transition-all duration-200 hover:bg-slate-100 hover:shadow-sm
              flex-1
            "
          >
            {/* 股票名称 */}
            <div className="text-sm font-bold text-slate-700 min-w-[70px]">
              {item.name}
            </div>

            {/* 合并的涨跌幅信息 */}
            <div className="flex-1 text-center">
              {item.changePercent !== undefined && item.change !== undefined && (
                <div className={`text-sm font-bold font-mono ${
                  item.changePercent > 0
                    ? 'text-[var(--profit-primary)]'
                    : item.changePercent < 0
                      ? 'text-[var(--loss-primary)]'
                      : 'text-slate-500'
                }`}>
                  {item.changePercent > 0 ? '+' : ''}{item.changePercent.toFixed(2)}% ({item.change > 0 ? '+' : ''}{item.change?.toFixed(2)})
                </div>
              )}
            </div>

            {/* 大盘指数 - 移至最右侧 */}
            <div className="text-sm font-black text-slate-800 min-w-[80px] text-right font-mono">
              {item.price?.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};
