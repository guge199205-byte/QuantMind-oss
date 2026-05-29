/**
 * 实时行情卡片 - Week 9 Day 1
 * 显示单个股票的实时行情信息
 */

import React, { useEffect, useState } from 'react';
import { Quote } from '../../services/market/MarketDataService';
import { formatBackendTime } from '../../utils/format';

export interface RealtimeQuoteCardProps {
  quote: Quote;
  onClick?: () => void;
  showDetail?: boolean;
}

export const RealtimeQuoteCard: React.FC<RealtimeQuoteCardProps> = ({
  quote,
  onClick,
  showDetail = false
}) => {
  const [priceFlash, setPriceFlash] = useState<'up' | 'down' | null>(null);
  const [prevPrice, setPrevPrice] = useState(quote.price);

  useEffect(() => {
    if (quote.price !== prevPrice) {
      setPriceFlash(quote.price > prevPrice ? 'up' : 'down');
      setPrevPrice(quote.price);

      // 清除闪烁效果
      const timer = setTimeout(() => {
        setPriceFlash(null);
      }, 500);

      return () => clearTimeout(timer);
    }
  }, [quote.price]);

  const isUp = quote.change >= 0;
  const changeColor = isUp ? '#f5222d' : '#52c41a';
  const flashColor = priceFlash === 'up' ? 'rgba(245, 34, 45, 0.2)' : priceFlash === 'down' ? 'rgba(82, 196, 26, 0.2)' : 'transparent';

  const formatNumber = (num: number, decimals = 2): string => {
    return num.toFixed(decimals);
  };

  const formatVolume = (vol: number): string => {
    if (vol >= 100000000) {
      return `${(vol / 100000000).toFixed(2)}亿`;
    } else if (vol >= 10000) {
      return `${(vol / 10000).toFixed(2)}万`;
    }
    return vol.toString();
  };

  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border transition-all ${onClick ? 'cursor-pointer hover:shadow-md' : ''}`}
      style={{
        borderColor: '#d9d9d9',
        backgroundColor: priceFlash ? flashColor : '#fff',
        transition: 'background-color 0.3s ease'
      }}
    >
      {/* 股票名称和代码 */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="font-semibold text-base">{quote.name}</div>
          <div className="text-xs text-gray-500">{quote.symbol}</div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold" style={{ color: changeColor }}>
            {formatNumber(quote.price)}
          </div>
        </div>
      </div>

      {/* 涨跌幅 */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-medium" style={{ color: changeColor }}>
          {isUp ? '+' : ''}{formatNumber(quote.change)}
        </span>
        <span className="text-sm font-medium" style={{ color: changeColor }}>
          {isUp ? '+' : ''}{formatNumber(quote.changePercent, 2)}%
        </span>
      </div>

      {/* 详细信息 */}
      {showDetail && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex justify-between">
            <span className="text-gray-500">开盘:</span>
            <span>{formatNumber(quote.open)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">最高:</span>
            <span style={{ color: '#f5222d' }}>{formatNumber(quote.high)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">最低:</span>
            <span style={{ color: '#52c41a' }}>{formatNumber(quote.low)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">昨收:</span>
            <span>{formatNumber(quote.close)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">成交量:</span>
            <span>{formatVolume(quote.volume)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">成交额:</span>
            <span>{formatVolume(quote.amount)}</span>
          </div>
          {quote.bidPrice && (
            <div className="flex justify-between">
              <span className="text-gray-500">买一:</span>
              <span className="text-green-600">{formatNumber(quote.bidPrice)}</span>
            </div>
          )}
          {quote.askPrice && (
            <div className="flex justify-between">
              <span className="text-gray-500">卖一:</span>
              <span className="text-red-600">{formatNumber(quote.askPrice)}</span>
            </div>
          )}
        </div>
      )}

      {/* 时间戳 */}
      <div className="mt-2 text-xs text-gray-400 text-right">
        {formatBackendTime(quote.timestamp, { withSeconds: false })}
      </div>
    </div>
  );
};

export default RealtimeQuoteCard;
