/**
 * 绩效分析面板
 *
 * 展示月度/季度/年度收益与滚动指标、收益分位数
 */

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Info,
  RefreshCw,
  TrendingUp,
  Activity,
  BarChart3,
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import {
  advancedAnalysisService,
  type PerformanceResponse,
  type MonthlyReturn,
  type TimeSeriesData,
} from '../../../services/advancedAnalysisService';

interface PerformancePanelProps {
  backtestId: string;
}

export const PerformancePanel: React.FC<PerformancePanelProps> = ({ backtestId }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PerformanceResponse | null>(null);
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
      const result = await advancedAnalysisService.analyzePerformance(backtestId);
      setData(result);
    } catch (err: any) {
      setError(err.message || '分析失败');
      console.error('加载绩效分析数据失败:', err);
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

  const safeData = useMemo(() => sanitizePerformanceData(data), [data]);
  const getMarketColor = (value: number): 'red' | 'green' => (value >= 0 ? 'red' : 'green');
  const yearlyReturnColor: 'red' | 'green' = getMarketColor(safeData.yearly_return);
  const p05Color: 'red' | 'green' = getMarketColor(safeData.return_percentiles.p05);
  const p95Color: 'red' | 'green' = getMarketColor(safeData.return_percentiles.p95);

  const metrics = [
    {
      label: '年度收益率',
      value: safeData.yearly_return,
      format: 'percent' as const,
      icon: TrendingUp,
      color: yearlyReturnColor,
    },
    {
      label: '滚动窗口',
      value: safeData.rolling_window,
      format: 'number' as const,
      icon: Activity,
      color: 'gray' as const,
      decimals: 0,
      suffix: '天',
    },
    {
      label: '收益中位数',
      value: safeData.return_percentiles.p50,
      format: 'percent' as const,
      icon: BarChart3,
      color: 'gray' as const,
    },
    {
      label: '收益P05',
      value: safeData.return_percentiles.p05,
      format: 'percent' as const,
      icon: TrendingUp,
      color: p05Color,
    },
    {
      label: '收益P95',
      value: safeData.return_percentiles.p95,
      format: 'percent' as const,
      icon: TrendingUp,
      color: p95Color,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-blue-700">
            <div className="font-medium mb-1">绩效分析</div>
            <div>
              分析时间: {new Date(safeData.analyzed_at).toLocaleString()} | 滚动窗口: {safeData.rolling_window}天
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">月度收益热力图</h3>
          {safeData.monthly_returns.length > 0 ? (
            <ReactECharts
              option={getMonthlyReturnsHeatmapOption(safeData.monthly_returns)}
              style={{ height: '320px' }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <EmptyChart />
          )}
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">季度收益</h3>
          {Object.keys(safeData.quarterly_returns).length > 0 ? (
            <ReactECharts
              option={getQuarterlyReturnsOption(safeData.quarterly_returns)}
              style={{ height: '320px' }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <EmptyChart />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">滚动指标</h3>
          {safeData.rolling_return.dates.length > 0 ? (
            <ReactECharts
              option={getRollingMetricsOption(safeData)}
              style={{ height: '320px' }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <EmptyChart />
          )}
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">收益分位数</h3>
          <ReactECharts
            option={getPercentilesOption(safeData.return_percentiles)}
            style={{ height: '320px' }}
            opts={{ renderer: 'canvas' }}
          />
        </div>
      </div>
    </div>
  );
};

const DEFAULT_PERCENTILES = {
  p01: 0,
  p05: 0,
  p25: 0,
  p50: 0,
  p75: 0,
  p95: 0,
  p99: 0,
};

function sanitizePerformanceData(raw: PerformanceResponse): PerformanceResponse {
  const safeSeries = (series?: TimeSeriesData): TimeSeriesData => {
    const dates = Array.isArray(series?.dates) ? series!.dates : [];
    const values = Array.isArray(series?.values) ? series!.values : [];
    const length = Math.min(dates.length, values.length);
    return {
      dates: dates.slice(0, length),
      values: values.slice(0, length),
    };
  };

  return {
    monthly_returns: Array.isArray(raw.monthly_returns) ? raw.monthly_returns : [],
    quarterly_returns: raw.quarterly_returns ?? {},
    yearly_return: Number.isFinite(raw.yearly_return) ? raw.yearly_return : 0,
    rolling_sharpe: safeSeries(raw.rolling_sharpe),
    rolling_volatility: safeSeries(raw.rolling_volatility),
    rolling_return: safeSeries(raw.rolling_return),
    return_percentiles: raw.return_percentiles ?? DEFAULT_PERCENTILES,
    analyzed_at: raw.analyzed_at ?? new Date().toISOString(),
    rolling_window: Number.isFinite(raw.rolling_window) ? raw.rolling_window : 30,
  };
}

function getMonthlyReturnsHeatmapOption(data: MonthlyReturn[]) {
  const months = Array.from({ length: 12 }, (_, idx) => `${idx + 1}`);
  const years = Array.from(new Set(data.map((item) => item.year))).sort((a, b) => a - b);
  const map = new Map<string, number>();
  data.forEach((item) => {
    map.set(`${item.year}-${item.month}`, item.return_pct);
  });

  const seriesData: Array<[number, number, number | string]> = [];
  years.forEach((year, yIndex) => {
    months.forEach((month, mIndex) => {
      const value = map.get(`${year}-${mIndex + 1}`);
      seriesData.push([mIndex, yIndex, value ?? '-']);
    });
  });

  return {
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const value = params.value[2];
        const display = typeof value === 'number' ? `${(value * 100).toFixed(2)}%` : '暂无数据';
        return `${years[params.value[1]]}年${months[params.value[0]]}月<br/>收益: ${display}`;
      },
    },
    toolbox: {
      show: true,
      feature: {
        saveAsImage: { title: '保存图片' },
      },
    },
    grid: {
      left: '6%',
      right: '6%',
      bottom: '10%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: months,
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: years.map((year) => `${year}`),
      splitArea: { show: true },
    },
    visualMap: {
      min: -0.1,
      max: 0.1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
    },
    series: [
      {
        name: '月度收益',
        type: 'heatmap',
        data: seriesData,
        label: {
          show: true,
          formatter: (params: any) => {
            const value = params.value[2];
            return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '';
          },
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.3)',
          },
        },
      },
    ],
  };
}

function getQuarterlyReturnsOption(data: Record<string, number>) {
  const entries = Object.entries(data || {});
  entries.sort((a, b) => a[0].localeCompare(b[0]));
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const value = (params[0].value * 100).toFixed(2);
        return `${params[0].axisValue}<br/>季度收益: ${value}%`;
      },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { start: 0, end: 100, height: 16 },
    ],
    grid: {
      left: '6%',
      right: '6%',
      bottom: '16%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: entries.map(([label]) => label),
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: [
      {
        name: '季度收益',
        type: 'bar',
        data: entries.map(([, value]) => ({
          value,
          itemStyle: {
            color: value >= 0 ? '#3b82f6' : '#ef4444',
          },
        })),
        barMaxWidth: 32,
      },
    ],
  };
}

function getRollingMetricsOption(data: PerformanceResponse) {
  const dates = data.rolling_return.dates;
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const date = params[0]?.axisValue ?? '';
        const values = params
          .map((item: any) => {
            const value = item.seriesName.includes('收益')
              ? `${(item.value * 100).toFixed(2)}%`
              : item.value.toFixed(2);
            return `${item.seriesName}: ${value}`;
          })
          .join('<br/>');
        return `${date}<br/>${values}`;
      },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { start: 0, end: 100, height: 16 },
    ],
    grid: {
      left: '6%',
      right: '6%',
      bottom: '16%',
      top: '10%',
      containLabel: true,
    },
    legend: {
      data: ['滚动收益', '滚动夏普', '滚动波动率'],
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLabel: {
        formatter: (value: string) => {
          const index = dates.indexOf(value);
          return index % 30 === 0 ? value.slice(5, 10) : '';
        },
      },
    },
    yAxis: [
      {
        type: 'value',
        axisLabel: {
          formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
        },
      },
      {
        type: 'value',
        axisLabel: {
          formatter: (value: number) => value.toFixed(1),
        },
      },
    ],
    series: [
      {
        name: '滚动收益',
        type: 'line',
        data: data.rolling_return.values,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ef4444', width: 2 },
        yAxisIndex: 0,
      },
      {
        name: '滚动夏普',
        type: 'line',
        data: data.rolling_sharpe.values,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#f59e0b', width: 2 },
        yAxisIndex: 1,
      },
      {
        name: '滚动波动率',
        type: 'line',
        data: data.rolling_volatility.values,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#22c55e', width: 2 },
        yAxisIndex: 0,
      },
    ],
  };
}

function getPercentilesOption(data: PerformanceResponse['return_percentiles']) {
  const labels = ['P01', 'P05', 'P25', 'P50', 'P75', 'P95', 'P99'];
  const values = [data.p01, data.p05, data.p25, data.p50, data.p75, data.p95, data.p99];
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const value = (params[0].value * 100).toFixed(2);
        return `${params[0].axisValue}<br/>收益: ${value}%`;
      },
    },
    toolbox: {
      show: true,
      feature: {
        saveAsImage: { title: '保存图片' },
      },
    },
    grid: {
      left: '6%',
      right: '6%',
      bottom: '10%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: labels,
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: [
      {
        name: '收益分位数',
        type: 'bar',
        data: values.map((value) => ({
          value,
          itemStyle: {
            color: value >= 0 ? '#ef4444' : '#22c55e',
          },
        })),
        barMaxWidth: 28,
      },
    ],
  };
}

// Metric Card Component
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
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-2xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex flex-col items-center text-center relative overflow-hidden"
    >
      {Icon && (
        <div className={`absolute top-3 right-3 w-6 h-6 rounded-lg ${colorClasses[color]} flex items-center justify-center`}>
          <Icon className="w-3 h-3" />
        </div>
      )}
      <span className="text-xs text-gray-500 mb-1">{label}</span>
      <div className={`text-2xl font-bold ${colorClasses[color].split(' ')[0]}`}>
        {formattedValue}{suffix}
      </div>
    </motion.div>
  );
};

const EmptyChart: React.FC = () => {
  return (
    <div className="h-[320px] rounded-2xl border border-dashed border-gray-200 flex items-center justify-center text-sm text-gray-400">
      暂无数据
    </div>
  );
};
