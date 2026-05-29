/**
 * 富文本内容示例 - 展示如何使用各种富文本组件
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FinancialCard,
  StockQuoteCard,
  TrendChart,
  KLineChart,
  type FinancialMetric,
  type ChartDataPoint,
  type KLineData,
} from '../components/RichContent';

const RichContentExample: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'financial' | 'quote' | 'trend' | 'kline'>('financial');

  // 财报卡片示例数据
  const financialMetrics: FinancialMetric[] = [
    { label: '营业收入', value: 125000000000, unit: '元', change: 15.8, changeType: 'increase', highlight: true },
    { label: '净利润', value: 18500000000, unit: '元', change: 22.3, changeType: 'increase', highlight: true },
    { label: '净资产收益率', value: 18.5, unit: '%', change: 2.1, changeType: 'increase' },
    { label: '毛利率', value: 45.2, unit: '%', change: -1.2, changeType: 'decrease' },
    { label: '资产负债率', value: 35.8, unit: '%', change: -3.5, changeType: 'decrease' },
  ];

  // 趋势图示例数据
  const trendData: ChartDataPoint[] = [
    { name: '2023Q1', revenue: 28500, netProfit: 4200 },
    { name: '2023Q2', revenue: 31200, netProfit: 4800 },
    { name: '2023Q3', revenue: 29800, netProfit: 4500 },
    { name: '2023Q4', revenue: 35500, netProfit: 5000 },
    { name: '2024Q1', revenue: 33000, netProfit: 4900 },
    { name: '2024Q2', revenue: 36200, netProfit: 5500 },
  ];

  // K线图示例数据
  const klineData: KLineData[] = [
    { date: '2024-01-01', open: 100, close: 105, low: 98, high: 107, volume: 12500000 },
    { date: '2024-01-02', open: 105, close: 103, low: 102, high: 108, volume: 10800000 },
    { date: '2024-01-03', open: 103, close: 110, low: 102, high: 112, volume: 15600000 },
    { date: '2024-01-04', open: 110, close: 108, low: 106, high: 113, volume: 13200000 },
    { date: '2024-01-05', open: 108, close: 115, low: 107, high: 116, volume: 18900000 },
  ];

  const tabs = [
    { id: 'financial', label: '财报卡片' },
    { id: 'quote', label: '股票行情' },
    { id: 'trend', label: '趋势图表' },
    { id: 'kline', label: 'K线图' },
  ];

  return (
    <div className="w-full h-screen bg-gray-50 p-6 overflow-auto">
      <div className="max-w-7xl mx-auto">
        {/* 标题 */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">富文本内容示例</h1>
          <p className="text-gray-600">展示QuantBot支持的各种富文本渲染组件</p>
        </div>

        {/* 选项卡 */}
        <div className="flex gap-2 mb-6 border-b border-gray-200">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 font-medium transition-colors relative ${
                activeTab === tab.id
                  ? 'text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
              {activeTab === tab.id && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600"
                />
              )}
            </button>
          ))}
        </div>

        {/* 内容区域 */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {activeTab === 'financial' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <FinancialCard
                title="财务数据分析"
                subtitle="2024年第二季度"
                companyName="贵州茅台"
                tsCode="600519.SH"
                period="2024Q2"
                metrics={financialMetrics}
              />

              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-800">使用说明</h3>
                <div className="bg-white rounded-lg p-4 border border-gray-200 text-sm text-gray-700 space-y-2">
                  <p><strong>FinancialCard</strong> 组件用于展示财务数据卡片</p>
                  <p>• 支持多个财务指标展示</p>
                  <p>• 可显示变化率和趋势方向</p>
                  <p>• 支持高亮显示重要指标</p>
                  <p>• 自动格式化数字和百分比</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'quote' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <StockQuoteCard
                symbol="600519.SH"
                name="贵州茅台"
                price={1580.50}
                change={25.80}
                changePercent={1.66}
                volume={1250000}
                turnover={19750000000}
                high={1595.20}
                low={1565.30}
                open={1570.00}
                close={1554.70}
                timestamp="2024-12-25 15:00:00"
              />

              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-800">使用说明</h3>
                <div className="bg-white rounded-lg p-4 border border-gray-200 text-sm text-gray-700 space-y-2">
                  <p><strong>StockQuoteCard</strong> 组件用于展示股票实时行情</p>
                  <p>• 显示当前价格和涨跌幅</p>
                  <p>• 涨跌用不同颜色区分（红涨绿跌）</p>
                  <p>• 展示开盘价、最高价、最低价等</p>
                  <p>• 显示成交量和成交额</p>
                  <p>• 支持WebSocket实时更新</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'trend' && (
            <div className="space-y-6">
              <TrendChart
                title="营收与净利润趋势"
                subtitle="最近6个季度数据"
                data={trendData}
                series={[
                  { key: 'revenue', name: '营业收入', color: '#3b82f6' },
                  { key: 'netProfit', name: '净利润', color: '#10b981' },
                ]}
                type="line"
                height={300}
              />

              <TrendChart
                title="营收对比（柱状图）"
                subtitle="最近6个季度"
                data={trendData}
                series={[
                  { key: 'revenue', name: '营业收入', color: '#8b5cf6' },
                ]}
                type="bar"
                height={300}
              />

              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-800 mb-3">使用说明</h3>
                <div className="text-sm text-gray-700 space-y-2">
                  <p><strong>TrendChart</strong> 组件基于 Recharts，支持多种图表类型</p>
                  <p>• <strong>line</strong>: 折线图，适合展示趋势</p>
                  <p>• <strong>area</strong>: 面积图，强调数值变化</p>
                  <p>• <strong>bar</strong>: 柱状图，适合对比数据</p>
                  <p>• 支持多系列数据展示</p>
                  <p>• 自带交互式工具提示</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'kline' && (
            <div className="space-y-6">
              <KLineChart
                title="贵州茅台 K线图"
                subtitle="600519.SH - 日K"
                data={klineData}
                height={500}
              />

              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-800 mb-3">使用说明</h3>
                <div className="text-sm text-gray-700 space-y-2">
                  <p><strong>KLineChart</strong> 组件基于 ECharts，专门用于展示K线图</p>
                  <p>• 显示开盘、收盘、最高、最低价格</p>
                  <p>• 包含成交量柱状图</p>
                  <p>• 支持数据缩放和拖拽查看</p>
                  <p>• 红色表示上涨，绿色表示下跌</p>
                  <p>• 鼠标悬停显示详细数据</p>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
};

export default RichContentExample;
