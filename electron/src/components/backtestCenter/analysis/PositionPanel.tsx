/**
 * 持仓分析面板
 */

import React, { useEffect, useState } from 'react';
import { AlertTriangle, Info, Layers, PieChart, RefreshCw } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import {
  advancedAnalysisService,
  type PositionAnalysisResponse,
} from '../../../services/advancedAnalysisService';

interface PositionPanelProps {
  backtestId: string;
}

export const PositionPanel: React.FC<PositionPanelProps> = ({ backtestId }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PositionAnalysisResponse | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (backtestId) {
      loadData();
    }
  }, [backtestId]);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await advancedAnalysisService.analyzePosition(backtestId);
      setData(result);
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
      console.error('加载持仓分析失败:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
          <p className="text-sm text-gray-600">正在分析...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" />
          <div>
            <div className="font-medium text-red-800">分析失败</div>
            <div className="text-sm text-red-700 mt-1">{error}</div>
            <button
              onClick={loadData}
              className="mt-2 text-sm text-red-600 hover:text-red-700 underline"
            >
              重试
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center text-gray-500 py-12">
        <Info className="w-12 h-12 mx-auto mb-2 opacity-50" />
        <p>选择回测结果后开始分析</p>
      </div>
    );
  }

  const topHolding = data.top_holdings[0];
  const sectorCount = data.sector_allocations.length;

  const metrics = [
    {
      label: '持仓数量',
      value: data.holdings_count,
      format: 'number' as const,
      icon: Layers,
      color: 'gray' as const,
      decimals: 0,
      suffix: '只',
    },
    {
      label: '集中度 HHI',
      value: data.concentration_hhi,
      format: 'number' as const,
      icon: PieChart,
      color: 'orange' as const,
      decimals: 3,
    },
    {
      label: 'Top1 权重',
      value: topHolding?.weight ?? 0,
      format: 'percent' as const,
      icon: Layers,
      color: 'red' as const,
    },
    {
      label: '行业数量',
      value: sectorCount,
      format: 'number' as const,
      icon: PieChart,
      color: 'purple' as const,
      decimals: 0,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-orange-600 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-orange-700">
            <div className="font-medium mb-1">持仓分析</div>
            <div>展示行业配置与头部持仓集中度。</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="行业配置分布">
          {data.sector_allocations.length > 0 ? (
            <ReactECharts
              option={getSectorAllocationOption(data)}
              style={{ height: '320px' }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <EmptyChart />
          )}
        </ChartCard>
        <ChartCard title="Top 10 持仓权重">
          {data.top_holdings.length > 0 ? (
            <ReactECharts
              option={getTopHoldingsOption(data)}
              style={{ height: '320px' }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <EmptyChart />
          )}
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <ChartCard title="行业收益贡献">
          {data.sector_allocations.length > 0 ? (
            <ReactECharts
              option={getSectorContributionOption(data)}
              style={{ height: '320px' }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <EmptyChart />
          )}
        </ChartCard>
      </div>
    </div>
  );
};

const ChartCard: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-4">{title}</h3>
      {children}
    </div>
  );
};

function getSectorAllocationOption(data: PositionAnalysisResponse) {
  const sectors = data.sector_allocations.map((item) => ({
    name: item.sector,
    value: item.weight,
  }));
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: { name: string; value: number }) => `${params.name}<br/>权重: ${(params.value * 100).toFixed(1)}%`,
    },
    series: [
      {
        name: '行业配置',
        type: 'pie',
        radius: ['35%', '70%'],
        data: sectors,
        label: { formatter: '{b}\n{d}%' },
      },
    ],
  };
}

function getTopHoldingsOption(data: PositionAnalysisResponse) {
  const sorted = [...data.top_holdings].sort((a, b) => b.weight - a.weight);
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ axisValue: string; value: number }>) => `${params[0].axisValue}<br/>权重: ${(params[0].value * 100).toFixed(2)}%`,
    },
    grid: { left: '8%', right: '6%', bottom: '10%', top: '10%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: (value: number) => `${(value * 100).toFixed(0)}%` } },
    yAxis: {
      type: 'category',
      data: sorted.map((item) => item.name ?? item.symbol),
    },
    series: [
      {
        name: '权重',
        type: 'bar',
        data: sorted.map((item) => item.weight),
        itemStyle: { color: '#ef4444' },
        barMaxWidth: 20,
      },
    ],
  };
}

function getSectorContributionOption(data: PositionAnalysisResponse) {
  const sectors = data.sector_allocations.map((item) => ({
    sector: item.sector,
    value: item.contribution ?? 0,
  }));
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ axisValue: string; value: number }>) => `${params[0].axisValue}<br/>贡献: ${params[0].value.toFixed(2)}`,
    },
    grid: { left: '6%', right: '6%', bottom: '10%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: sectors.map((item) => item.sector) },
    yAxis: { type: 'value' },
    series: [
      {
        name: '贡献',
        type: 'bar',
        data: sectors.map((item) => item.value),
        itemStyle: { color: '#6366f1' },
        barMaxWidth: 24,
      },
    ],
  };
}

interface MetricCardProps {
  label: string;
  value: number;
  format: 'percent' | 'number';
  icon?: React.ComponentType<{ className?: string }>;
  color?: 'blue' | 'green' | 'red' | 'orange' | 'purple' | 'gray';
  decimals?: number;
  suffix?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  format,
  icon: Icon,
  color = 'gray',
  decimals = 2,
  suffix = '',
}) => {
  const colorClasses = {
    blue: 'text-blue-600 bg-blue-50',
    green: 'text-green-600 bg-green-50',
    red: 'text-red-600 bg-red-50',
    orange: 'text-orange-600 bg-orange-50',
    purple: 'text-purple-600 bg-purple-50',
    gray: 'text-gray-600 bg-gray-50',
  };

  const formattedValue = format === 'percent'
    ? `${(value * 100).toFixed(decimals)}%`
    : value.toFixed(decimals);

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-600">{label}</span>
        {Icon && (
          <div className={`w-8 h-8 rounded-2xl ${colorClasses[color]} flex items-center justify-center`}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>
      <div className={`text-2xl font-bold ${colorClasses[color].split(' ')[0]}`}>
        {formattedValue}{suffix}
      </div>
    </div>
  );
};

const EmptyChart: React.FC = () => {
  return (
    <div className="h-[320px] rounded-2xl border border-dashed border-gray-200 flex items-center justify-center text-sm text-gray-400">
      暂无数据
    </div>
  );
};

function extractErrorMessage(error: unknown): string {
  const err = error as {
    message?: string;
    response?: { data?: { detail?: string } };
  };
  return err?.response?.data?.detail || err?.message || '分析失败';
}
