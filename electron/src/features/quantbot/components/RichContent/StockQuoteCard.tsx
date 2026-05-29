/**
 * 股票行情卡片组件
 */

import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';

export interface StockQuoteProps {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume?: number;
  turnover?: number;
  high?: number;
  low?: number;
  open?: number;
  close?: number;
  timestamp?: string;
}

const StockQuoteCard: React.FC<StockQuoteProps> = ({
  symbol,
  name,
  price,
  change,
  changePercent,
  volume,
  turnover,
  high,
  low,
  open,
  close,
  timestamp,
}) => {
  const isPositive = change >= 0;

  const formatNumber = (num: number | undefined, decimals: number = 2): string => {
    if (num === undefined) return '--';
    return num.toLocaleString('zh-CN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatVolume = (vol: number | undefined): string => {
    if (vol === undefined) return '--';
    if (vol >= 100000000) {
      return `${(vol / 100000000).toFixed(2)}亿`;
    } else if (vol >= 10000) {
      return `${(vol / 10000).toFixed(2)}万`;
    }
    return vol.toString();
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden"
    >
      {/* 头部 - 股票信息 */}
      <div className={`p-4 ${
        isPositive
          ? 'bg-gradient-to-r from-red-500 to-red-600'
          : 'bg-gradient-to-r from-green-500 to-green-600'
      } text-white`}>
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-xl font-bold">{name}</h3>
            <p className="text-sm opacity-90 mt-1">{symbol}</p>
          </div>
          {isPositive ? (
            <TrendingUp className="w-8 h-8" />
          ) : (
            <TrendingDown className="w-8 h-8" />
          )}
        </div>

        {/* 当前价格 */}
        <div className="mt-4">
          <div className="text-3xl font-bold">¥{formatNumber(price)}</div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-lg font-medium">
              {isPositive ? '+' : ''}{formatNumber(change)}
            </span>
            <span className="text-lg font-medium">
              ({isPositive ? '+' : ''}{formatNumber(changePercent)}%)
            </span>
          </div>
        </div>

        {timestamp && (
          <div className="text-xs opacity-75 mt-2">
            更新时间: {timestamp}
          </div>
        )}
      </div>

      {/* 详细数据 */}
      <div className="p-4 grid grid-cols-2 gap-4">
        {open !== undefined && (
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">今开</span>
            <span className="text-sm font-semibold text-gray-900 mt-1">
              {formatNumber(open)}
            </span>
          </div>
        )}

        {close !== undefined && (
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">昨收</span>
            <span className="text-sm font-semibold text-gray-900 mt-1">
              {formatNumber(close)}
            </span>
          </div>
        )}

        {high !== undefined && (
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">最高</span>
            <span className="text-sm font-semibold text-red-600 mt-1">
              {formatNumber(high)}
            </span>
          </div>
        )}

        {low !== undefined && (
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">最低</span>
            <span className="text-sm font-semibold text-green-600 mt-1">
              {formatNumber(low)}
            </span>
          </div>
        )}

        {volume !== undefined && (
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">成交量</span>
            <span className="text-sm font-semibold text-gray-900 mt-1">
              {formatVolume(volume)}
            </span>
          </div>
        )}

        {turnover !== undefined && (
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">成交额</span>
            <span className="text-sm font-semibold text-gray-900 mt-1">
              {formatVolume(turnover)}元
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default StockQuoteCard;
