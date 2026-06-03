import React from 'react';
import { Card } from '../common/Card';
import { MarketOverviewSkeleton } from '../common/CardSkeletons';
import { useMarketData } from '../../hooks/useMarketData';
import { useAppSelector } from '../../store';
import { selectCurrentMarket } from '../../store/slices/uiSlice';
import { MARKET_INDICES, type MarketId } from '../../services/marketService';
import type { MarketIndex } from '../../services/marketService';

const MARKET_LABELS: Record<MarketId, string> = {
  CN: 'A股',
  HK: '港股',
  US: '美股',
  CRYPTO: '区块链',
};

export const MarketOverviewCard: React.FC = () => {
  const currentMarket = useAppSelector(selectCurrentMarket);
  const { data, loading, error } = useMarketData({ market: currentMarket });

  // 市场默认数据
  const fallbackData: Partial<MarketIndex>[] = (MARKET_INDICES[currentMarket] || MARKET_INDICES.CN).map(
    ({ name, basePrice }) => ({ name, price: basePrice, change: 0, changePercent: 0 })
  );

  if (loading) {
    return <MarketOverviewSkeleton />;
  }

  if (error) {
    console.error('获取市场数据出错:', error);
  }

  const displayData = data?.indices || fallbackData;

  return (
    <Card title={`${MARKET_LABELS[currentMarket]}概览`} height="100%" background="market">
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
