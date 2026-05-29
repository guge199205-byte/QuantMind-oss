/**
 * 各仪表盘卡片的骨架屏组件
 * 形状与真实内容一致，替代通用 Loading spinner，消除数据加载期间的灰屏感。
 */
import React from 'react';
import { Card } from './Card';

// 基础闪烁块
const Shimmer: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse bg-gray-200/60 rounded-lg ${className}`} />
);

// ── 大盘概览：6行指数列表 ──────────────────────────────────────────
export const MarketOverviewSkeleton: React.FC = () => (
  <Card title="大盘概览" height="100%">
    <div className="flex flex-col justify-between h-full py-2 gap-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center justify-between px-3 py-3 rounded-lg bg-gray-50/40 flex-1">
          <Shimmer className="w-16 h-4" />
          <Shimmer className="w-24 h-4" />
          <Shimmer className="w-16 h-4" />
        </div>
      ))}
    </div>
  </Card>
);

// ── 资金概览：大数字 + 4项指标 ────────────────────────────────────
export const FundOverviewSkeleton: React.FC = () => (
  <Card title="资金概览" background="fund" height="100%">
    {/* 总资产大数字 */}
    <div className="flex flex-col items-center gap-2 mb-4">
      <Shimmer className="w-40 h-10" />
      <Shimmer className="w-24 h-4" />
    </div>
    {/* 4 项指标格 */}
    <div className="grid grid-cols-2 gap-3 mb-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-xl bg-white/40 p-3 flex flex-col gap-2">
          <Shimmer className="w-14 h-3" />
          <Shimmer className="w-20 h-5" />
        </div>
      ))}
    </div>
    {/* 底部进度条区域 */}
    <div className="flex flex-col gap-2 mt-auto">
      <Shimmer className="w-full h-2 rounded-full" />
      <div className="flex justify-between">
        <Shimmer className="w-12 h-3" />
        <Shimmer className="w-12 h-3" />
      </div>
    </div>
  </Card>
);

// ── 交易记录：表头 + 5行记录 ──────────────────────────────────────
export const TradeRecordsSkeleton: React.FC = () => (
  <Card title="交易记录" height="100%">
    {/* 筛选条 */}
    <div className="flex gap-2 mb-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Shimmer key={i} className="w-16 h-7 rounded-full" />
      ))}
    </div>
    {/* 表头 */}
    <div className="grid mb-2" style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr))' }}>
      {['w-10', 'w-10', 'w-12', 'w-10', 'w-12'].map((w, i) => (
        <Shimmer key={i} className={`${w} h-3 mx-auto`} />
      ))}
    </div>
    {/* 5 行数据 */}
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="grid items-center px-2 py-2 rounded-lg bg-gray-50/40"
          style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr))' }}
        >
          <Shimmer className="w-12 h-4 mx-auto" />
          <Shimmer className="w-8 h-4 mx-auto" />
          <Shimmer className="w-full h-4 mx-auto" />
          <Shimmer className="w-14 h-4 mx-auto" />
          <Shimmer className="w-16 h-4 mx-auto" />
        </div>
      ))}
    </div>
  </Card>
);

// ── 策略监控：状态徽标 + 3条策略 ─────────────────────────────────
export const StrategyMonitorSkeleton: React.FC = () => (
  <div className="w-full h-full rounded-2xl p-1 bg-white/60 border border-white/40 shadow-sm flex flex-col p-4 gap-3">
    {/* 标题行 */}
    <div className="flex items-center justify-between">
      <Shimmer className="w-24 h-5" />
      <Shimmer className="w-16 h-6 rounded-full" />
    </div>
    {/* 3 条策略 */}
    {Array.from({ length: 3 }).map((_, i) => (
      <div key={i} className="rounded-xl bg-gray-50/50 p-3 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <Shimmer className="w-28 h-4" />
          <Shimmer className="w-12 h-5 rounded-full" />
        </div>
        <div className="flex gap-4">
          <Shimmer className="w-20 h-3" />
          <Shimmer className="w-16 h-3" />
          <Shimmer className="w-14 h-3" />
        </div>
        <Shimmer className="w-full h-1.5 rounded-full" />
      </div>
    ))}
    {/* 底部操作 */}
    <div className="mt-auto flex justify-end">
      <Shimmer className="w-20 h-7 rounded-lg" />
    </div>
  </div>
);

// ── 智能图表：图表区域占位 ────────────────────────────────────────
export const IntelligenceChartsSkeleton: React.FC = () => (
  <Card title="智能图表" height="100%">
    {/* 股票选择器 */}
    <div className="flex gap-2 mb-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <Shimmer key={i} className="w-16 h-7 rounded-full" />
      ))}
    </div>
    {/* K线图主区域 */}
    <div className="relative w-full flex-1 rounded-xl bg-gray-50/40 overflow-hidden" style={{ height: 'calc(100% - 80px)' }}>
      <div className="animate-pulse w-full h-full flex flex-col justify-end px-3 pb-4 gap-1">
        {/* 模拟 K线柱 */}
        {[60, 75, 50, 85, 65, 90, 70, 55, 80, 45, 70, 88].map((h, i) => (
          <div key={i} className="absolute bottom-4" style={{ left: `${6 + i * 7.5}%`, width: '5%', height: `${h}%`, background: i % 2 === 0 ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)', borderRadius: 2 }} />
        ))}
        {/* 模拟折线 */}
        <svg className="absolute inset-0 w-full h-full opacity-20" xmlns="http://www.w3.org/2000/svg">
          <polyline points="5%,70% 15%,55% 25%,65% 35%,40% 45%,50% 55%,30% 65%,45% 75%,35% 85%,25% 95%,20%" fill="none" stroke="#3b82f6" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
    </div>
  </Card>
);

// ── 通知中心：3条通知 ─────────────────────────────────────────────
export const NotificationSkeleton: React.FC = () => (
  <div className="w-full h-full rounded-2xl p-1 bg-white/60 border border-white/40 shadow-sm flex flex-col p-4 gap-3">
    {/* 标题行 */}
    <div className="flex items-center justify-between">
      <Shimmer className="w-20 h-5" />
      <Shimmer className="w-10 h-5 rounded-full" />
    </div>
    {/* 分类 tabs */}
    <div className="flex gap-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <Shimmer key={i} className="w-14 h-6 rounded-full" />
      ))}
    </div>
    {/* 4 条通知 */}
    {Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="flex gap-3 items-start rounded-xl bg-gray-50/50 p-3">
        <Shimmer className="w-8 h-8 rounded-full shrink-0" />
        <div className="flex-1 flex flex-col gap-1.5">
          <Shimmer className="w-3/4 h-3.5" />
          <Shimmer className="w-1/2 h-3" />
        </div>
        <Shimmer className="w-10 h-3 shrink-0" />
      </div>
    ))}
    <div className="mt-auto flex justify-end">
      <Shimmer className="w-20 h-7 rounded-lg" />
    </div>
  </div>
);
