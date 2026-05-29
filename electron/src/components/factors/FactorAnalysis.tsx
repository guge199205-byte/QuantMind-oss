/**
 * 因子分析组件
 * 展示因子的统计信息和分布
 */

import React from 'react';
import { TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { FactorData } from '../../services/qlib/qlibDataService';

interface Props {
  factor: FactorData;
}

export const FactorAnalysis: React.FC<Props> = ({ factor }) => {
  const values = factor.data.map(d => d.value).filter(v => v !== null) as number[];

  if (values.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500">
        暂无数据
      </div>
    );
  }

  // 统计指标
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const sorted = [...values].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const std = Math.sqrt(values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length);

  // 分布直方图
  const histogramOption = {
    title: { text: '因子分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: '10%', right: '10%', top: '20%', bottom: '15%' },
    xAxis: { type: 'value', name: '因子值' },
    yAxis: { type: 'value', name: '频数' },
    series: [{
      type: 'bar',
      data: (() => {
        const bins = 20;
        const binSize = (max - min) / bins;
        const histogram = Array(bins).fill(0);
        values.forEach(v => {
          const binIndex = Math.min(Math.floor((v - min) / binSize), bins - 1);
          histogram[binIndex]++;
        });
        return histogram.map((count, i) => [min + i * binSize + binSize / 2, count]);
      })(),
      itemStyle: { color: '#3b82f6' }
    }]
  };

  return (
    <div className="space-y-4">
      {/* 统计卡片 */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">均值</div>
          <div className="text-lg font-bold text-gray-800">{mean.toFixed(4)}</div>
        </div>
        <div className="bg-white border rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">中位数</div>
          <div className="text-lg font-bold text-gray-800">{median.toFixed(4)}</div>
        </div>
        <div className="bg-white border rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">标准差</div>
          <div className="text-lg font-bold text-gray-800">{std.toFixed(4)}</div>
        </div>
        <div className="bg-white border rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">最小值</div>
          <div className="text-lg font-bold text-green-600">{min.toFixed(4)}</div>
        </div>
        <div className="bg-white border rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">最大值</div>
          <div className="text-lg font-bold text-red-600">{max.toFixed(4)}</div>
        </div>
        <div className="bg-white border rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">样本数</div>
          <div className="text-lg font-bold text-gray-800">{values.length}</div>
        </div>
      </div>

      {/* 直方图 */}
      <div className="bg-white border rounded-lg p-4">
        <ReactECharts option={histogramOption} style={{ height: '250px', width: '100%' }} />
      </div>
    </div>
  );
};
