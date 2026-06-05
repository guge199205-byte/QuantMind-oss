/**
 * 模型评估模块 — 滚动回测评估模型预测质量
 *
 * 功能：
 * - 选择模型 + 日期范围 + 预测周期
 * - 运行滚动回测，对比预测分数与实际收益
 * - 展示 IC、IC_IR、命中率、十分位收益等指标
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Select, DatePicker, Button, Space, Spin, message,
  Row, Col, Statistic, Table, Typography, Divider, Empty, Popconfirm,
} from 'antd';
import {
  BarChart3, TrendingUp, Activity, Target, Zap, Trash2, RotateCcw,
} from 'lucide-react';
import dayjs from 'dayjs';
import ReactECharts from 'echarts-for-react';
import { modelTrainingService } from '../../services/modelTrainingService';

const { RangePicker } = DatePicker;
const { Text } = Typography;

interface ModelInfo {
  model_id: string;
  model_dir: string;
  framework: string;
  feature_count: number;
  target_horizon_days: number;
  metrics: Record<string, any>;
  type: string;
}

interface BacktestResult {
  status: string;
  model_id: string;
  horizon: number;
  metrics: {
    ic_mean: number;
    ic_std: number;
    ic_ir: number;
    hit_rate: number;
    n_dates: number;
    avg_top_decile: number;
    avg_bottom_decile: number;
    long_short_return: number;
    monotonicity: number;
    decile_rank_ic: number;
  };
  avg_decile_returns: Record<number, number>;
  per_day: Array<{
    date: string;
    ic: number;
    n_stocks: number;
    decile_returns: Record<number, number>;
    top_10pct_return: number;
    bottom_10pct_return: number;
  }>;
  errors: Array<{ date: string; error: string }>;
}

interface ModelEvaluationModuleProps {
  initialModelId?: string;
  compact?: boolean;
}

export const ModelEvaluationModule: React.FC<ModelEvaluationModuleProps> = ({ initialModelId, compact }) => {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(initialModelId || '');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(6, 'month'),
    dayjs().subtract(1, 'day'),
  ]);
  const [horizon, setHorizon] = useState<number>(10);
  const [sampleInterval, setSampleInterval] = useState<number>(3);
  const [loading, setLoading] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string>('');
  const [multiHorizonResult, setMultiHorizonResult] = useState<any>(null);
  const [multiHorizonLoading, setMultiHorizonLoading] = useState(false);

  useEffect(() => {
    loadModels();
  }, []);

  // Load history when model changes
  useEffect(() => {
    if (selectedModelId) {
      loadHistory(selectedModelId);
    } else {
      setHistory([]);
      setResult(null);
    }
  }, [selectedModelId]);

  const loadModels = async () => {
    setModelsLoading(true);
    try {
      const list = await modelTrainingService.listModelsForBacktest();
      setModels(list);
    } catch (e: any) {
      message.error('加载模型列表失败: ' + (e.message || '未知错误'));
    } finally {
      setModelsLoading(false);
    }
  };

  const loadHistory = async (modelId: string) => {
    setHistoryLoading(true);
    try {
      const records = await modelTrainingService.getBacktestHistory(modelId);
      setHistory(records);
      // Auto-load latest result
      if (records.length > 0 && !result) {
        loadDetail(modelId, records[0].run_id);
      }
    } catch (e: any) {
      // Silent fail for history
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadDetail = async (modelId: string, runId: string) => {
    try {
      const detail = await modelTrainingService.getBacktestDetail(modelId, runId);
      setResult(detail);
      setActiveRunId(runId);
    } catch (e: any) {
      message.error('加载回测详情失败');
    }
  };

  const deleteHistoryItem = async (runId: string) => {
    try {
      await modelTrainingService.deleteBacktestHistory(selectedModelId, runId);
      setHistory(prev => prev.filter(h => h.run_id !== runId));
      if (activeRunId === runId) {
        setResult(null);
        setActiveRunId('');
      }
      message.success('已删除');
    } catch (e: any) {
      message.error('删除失败');
    }
  };

  const runBacktest = async () => {
    if (!selectedModelId) {
      message.warning('请选择模型');
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const resp = await modelTrainingService.runModelBacktest({
        model_id: selectedModelId,
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
        horizon,
        sample_interval: sampleInterval,
      });
      if (resp.status === 'success') {
        setResult(resp);
        setActiveRunId(resp.run_id || '');
        message.success(`回测完成，共 ${resp.metrics.n_dates} 个交易日`);
        // Reload history
        loadHistory(selectedModelId);
      } else {
        message.error(resp.error || '回测失败');
      }
    } catch (e: any) {
      message.error('回测请求失败: ' + (e.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  const runMultiHorizonBacktest = async () => {
    if (!selectedModelId) {
      message.warning('请选择模型');
      return;
    }
    setMultiHorizonLoading(true);
    setMultiHorizonResult(null);
    try {
      const resp = await modelTrainingService.runMultiHorizonBacktest({
        model_id: selectedModelId,
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
        horizons: [1, 5, 10, 20],
        sample_interval: sampleInterval,
      });
      if (resp.status === 'success') {
        setMultiHorizonResult(resp);
        message.success('多周期对比回测完成');
      } else {
        message.error(resp.error || '多周期回测失败');
      }
    } catch (e: any) {
      message.error('多周期回测请求失败: ' + (e.message || '未知错误'));
    } finally {
      setMultiHorizonLoading(false);
    }
  };

  // IC 时间序列图
  const icChartOption = result ? {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(0,0,0,0.1)',
      textStyle: { color: '#374151' },
      formatter: (params: any) => {
        const p = params[0];
        return `${p.axisValue}<br/>IC: ${(p.value as number).toFixed(4)}`;
      },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: result.per_day.map(d => d.date),
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280', rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [
      {
        name: 'IC',
        type: 'line',
        data: result.per_day.map(d => d.ic),
        smooth: true,
        lineStyle: { width: 2, color: '#3b82f6' },
        itemStyle: { color: '#3b82f6' },
        areaStyle: {
          color: {
            type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.2)' },
              { offset: 1, color: 'rgba(59,130,246,0.02)' },
            ],
          },
        },
        markLine: {
          silent: true,
          data: [{ yAxis: 0, lineStyle: { color: '#ef4444', type: 'dashed' as const, width: 1 } }],
        },
      },
    ],
  } : null;

  // 十分位收益柱状图
  const decileChartOption = result ? {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(0,0,0,0.1)',
      textStyle: { color: '#374151' },
      formatter: (params: any) => {
        const p = params[0];
        return `Decile ${p.axisValue}<br/>平均收益: ${((p.value as number) * 100).toFixed(2)}%`;
      },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: Array.from({ length: 10 }, (_, i) => `D${i + 1}`),
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280', formatter: (v: number) => `${(v * 100).toFixed(1)}%` },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [{
      name: '平均收益',
      type: 'bar',
      data: Array.from({ length: 10 }, (_, i) => result.avg_decile_returns[i] ?? 0),
      itemStyle: {
        color: (params: any) => {
          const val = params.value as number;
          return val >= 0 ? '#ef4444' : '#22c55e';
        },
        borderRadius: [4, 4, 0, 0],
      },
    }],
  } : null;

  // Per-day table columns
  const columns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    {
      title: 'IC', dataIndex: 'ic', key: 'ic', width: 100,
      render: (v: number) => (
        <span style={{ color: v > 0 ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
          {v.toFixed(4)}
        </span>
      ),
    },
    { title: '股票数', dataIndex: 'n_stocks', key: 'n_stocks', width: 80 },
    {
      title: 'Top 10%', dataIndex: 'top_10pct_return', key: 'top10', width: 100,
      render: (v: number) => (
        <span style={{ color: v > 0 ? '#ef4444' : '#22c55e' }}>
          {(v * 100).toFixed(2)}%
        </span>
      ),
    },
    {
      title: 'Bottom 10%', dataIndex: 'bottom_10pct_return', key: 'bottom10', width: 100,
      render: (v: number) => (
        <span style={{ color: v > 0 ? '#ef4444' : '#22c55e' }}>
          {(v * 100).toFixed(2)}%
        </span>
      ),
    },
    {
      title: '多空收益', key: 'ls', width: 100,
      render: (_: any, record: any) => {
        const ls = (record.top_10pct_return || 0) - (record.bottom_10pct_return || 0);
        return (
          <span style={{ color: ls > 0 ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
            {(ls * 100).toFixed(2)}%
          </span>
        );
      },
    },
  ];

  const metricCards = result?.metrics ? [
    {
      label: 'IC 均值',
      value: result.metrics.ic_mean.toFixed(4),
      icon: Activity,
      color: result.metrics.ic_mean > 0.03 ? 'text-green-600' : result.metrics.ic_mean > 0 ? 'text-yellow-600' : 'text-red-600',
      desc: `预测与实际收益的秩相关（随机基准: ${result.metrics.random_ic_mean?.toFixed(4) || '0'}）`,
    },
    {
      label: 'IC_IR',
      value: result.metrics.ic_ir.toFixed(2),
      icon: Zap,
      color: result.metrics.ic_ir > 0.5 ? 'text-green-600' : result.metrics.ic_ir > 0 ? 'text-yellow-600' : 'text-red-600',
      desc: 'IC均值/IC标准差，衡量稳定性（>0.5为佳）',
    },
    {
      label: '命中率',
      value: `${(result.metrics.hit_rate * 100).toFixed(1)}%`,
      icon: Target,
      color: result.metrics.hit_rate > 0.55 ? 'text-green-600' : result.metrics.hit_rate > 0.5 ? 'text-yellow-600' : 'text-red-600',
      desc: 'IC > 0 的日期占比（随机为50%）',
    },
    {
      label: '多空收益',
      value: `${(result.metrics.long_short_return * 100).toFixed(2)}%`,
      icon: TrendingUp,
      color: result.metrics.long_short_return > 0 ? 'text-green-600' : 'text-red-600',
      desc: 'Top十分位 - Bottom十分位平均收益',
    },
  ] : [];

  // 累积IC曲线
  const cumulativeICOption = result?.metrics?.cumulative_ic ? {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(0,0,0,0.1)',
      textStyle: { color: '#374151' },
      formatter: (params: any) => {
        const p = params[0];
        return `${p.axisValue}<br/>累积IC: ${(p.value as number).toFixed(4)}`;
      },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: result.per_day.map(d => d.date),
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280', rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [{
      name: '累积IC',
      type: 'line',
      data: result.metrics.cumulative_ic,
      smooth: true,
      lineStyle: { width: 2, color: '#8b5cf6' },
      itemStyle: { color: '#8b5cf6' },
      areaStyle: {
        color: {
          type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(139,92,246,0.2)' },
            { offset: 1, color: 'rgba(139,92,246,0.02)' },
          ],
        },
      },
    }],
  } : null;

  // 月度IC分布
  const monthlyICOption = result?.metrics?.monthly_ic ? (() => {
    const months = Object.keys(result.metrics.monthly_ic).sort();
    const values = months.map(m => result.metrics.monthly_ic[m]);
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis' as const,
        backgroundColor: 'rgba(255,255,255,0.95)',
        borderColor: 'rgba(0,0,0,0.1)',
        textStyle: { color: '#374151' },
        formatter: (params: any) => {
          const p = params[0];
          return `${p.axisValue}<br/>月度IC: ${(p.value as number).toFixed(4)}`;
        },
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
      xAxis: {
        type: 'category' as const,
        data: months,
        axisLine: { lineStyle: { color: '#d1d5db' } },
        axisLabel: { color: '#6b7280', rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'value' as const,
        axisLine: { lineStyle: { color: '#d1d5db' } },
        axisLabel: { color: '#6b7280' },
        splitLine: { lineStyle: { color: '#e5e7eb' } },
      },
      series: [{
        name: '月度IC',
        type: 'bar',
        data: values,
        itemStyle: {
          color: (params: any) => {
            const val = params.value as number;
            return val >= 0 ? '#ef4444' : '#22c55e';
          },
          borderRadius: [4, 4, 0, 0],
        },
      }],
    };
  })() : null;

  // 多空净值曲线
  const lsEquityOption = result?.metrics?.cumulative_ls ? {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(0,0,0,0.1)',
      textStyle: { color: '#374151' },
      formatter: (params: any) => {
        const p = params[0];
        return `${p.axisValue}<br/>累积多空收益: ${((p.value as number) * 100).toFixed(2)}%`;
      },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: result.per_day.map(d => d.date),
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280', rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280', formatter: (v: number) => `${(v * 100).toFixed(1)}%` },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [{
      name: '多空净值',
      type: 'line',
      data: result.metrics.cumulative_ls,
      smooth: true,
      lineStyle: { width: 2, color: '#f59e0b' },
      itemStyle: { color: '#f59e0b' },
      areaStyle: {
        color: {
          type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(245,158,11,0.2)' },
            { offset: 1, color: 'rgba(245,158,11,0.02)' },
          ],
        },
      },
      markLine: {
        silent: true,
        data: [{ yAxis: 0, lineStyle: { color: '#ef4444', type: 'dashed' as const, width: 1 } }],
      },
    }],
  } : null;

  return (
    <div className="space-y-6">
      {/* 配置面板 */}
      <Card title="回测配置" className="shadow-sm">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <Text className="text-xs text-gray-500 mb-1 block">选择模型</Text>
            <Select
              style={{ width: 280 }}
              placeholder="选择要评估的模型"
              value={selectedModelId || undefined}
              onChange={setSelectedModelId}
              loading={modelsLoading}
              showSearch
              optionFilterProp="label"
              options={models.map(m => ({
                value: m.model_id,
                label: `${m.model_id} (${m.framework}, ${m.feature_count}特征)`,
              }))}
            />
          </div>
          <div>
            <Text className="text-xs text-gray-500 mb-1 block">日期范围</Text>
            <RangePicker
              value={dateRange}
              onChange={(dates) => {
                if (dates && dates[0] && dates[1]) {
                  setDateRange([dates[0], dates[1]]);
                }
              }}
              format="YYYY-MM-DD"
            />
          </div>
          <div>
            <Text className="text-xs text-gray-500 mb-1 block">预测周期</Text>
            <Select
              style={{ width: 100 }}
              value={horizon}
              onChange={setHorizon}
              options={[
                { value: 5, label: 'T+5' },
                { value: 10, label: 'T+10' },
                { value: 20, label: 'T+20' },
              ]}
            />
          </div>
          <div>
            <Text className="text-xs text-gray-500 mb-1 block">采样间隔</Text>
            <Select
              style={{ width: 120 }}
              value={sampleInterval}
              onChange={setSampleInterval}
              options={[
                { value: 3, label: '每3个交易日' },
                { value: 5, label: '每5个交易日' },
                { value: 10, label: '每10个交易日' },
                { value: 20, label: '每20个交易日' },
              ]}
            />
          </div>
          <Button
            type="primary"
            icon={<BarChart3 className="w-4 h-4" />}
            onClick={runBacktest}
            loading={loading}
            disabled={!selectedModelId}
          >
            开始回测
          </Button>
          <Button
            icon={<BarChart3 className="w-4 h-4" />}
            onClick={runMultiHorizonBacktest}
            loading={multiHorizonLoading}
            disabled={!selectedModelId}
          >
            多周期对比
          </Button>
        </div>
      </Card>

      {/* 加载中 */}
      {(loading || multiHorizonLoading) && (
        <Card className="shadow-sm">
          <div className="flex items-center justify-center py-12">
            <Spin size="large" tip={multiHorizonLoading ? "正在执行多周期对比回测..." : "正在执行回测，请稍候..."} />
          </div>
        </Card>
      )}

      {/* 多周期对比回测结果 */}
      {multiHorizonResult && multiHorizonResult.status === 'success' && (
        <Card title="多周期对比回测结果" className="shadow-sm"
          extra={<Text className="text-xs text-gray-400">最佳周期: {multiHorizonResult.best_horizon}</Text>}
        >
          <Table
            dataSource={Object.entries(multiHorizonResult.horizons).map(([key, val]: [string, any]) => ({
              horizon: key,
              ...val,
            }))}
            rowKey="horizon"
            size="small"
            pagination={false}
            columns={[
              { title: '预测周期', dataIndex: 'horizon', key: 'horizon', width: 100 },
              {
                title: 'IC均值', key: 'ic', width: 100,
                render: (_: any, r: any) => r.ic_mean != null ? (
                  <span style={{ color: r.ic_mean > 0 ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                    {r.ic_mean.toFixed(4)}
                  </span>
                ) : r.error || '-',
              },
              {
                title: 'IC_IR', key: 'icir', width: 80,
                render: (_: any, r: any) => r.ic_ir?.toFixed(2) ?? '-',
              },
              {
                title: '命中率', key: 'hit', width: 80,
                render: (_: any, r: any) => r.hit_rate != null ? `${(r.hit_rate * 100).toFixed(0)}%` : '-',
              },
              {
                title: '多空收益', key: 'ls', width: 100,
                render: (_: any, r: any) => r.long_short_return != null ? (
                  <span style={{ color: r.long_short_return > 0 ? '#ef4444' : '#22c55e' }}>
                    {(r.long_short_return * 100).toFixed(2)}%
                  </span>
                ) : '-',
              },
              {
                title: 'Sharpe', key: 'sharpe', width: 80,
                render: (_: any, r: any) => r.sharpe_ls?.toFixed(2) ?? '-',
              },
              {
                title: '换手率', key: 'turnover', width: 80,
                render: (_: any, r: any) => r.turnover_mean != null ? `${(r.turnover_mean * 100).toFixed(0)}%` : '-',
              },
              { title: '天数', dataIndex: 'n_dates', key: 'n_dates', width: 60 },
            ]}
          />
        </Card>
      )}

      {/* 结果展示 */}
      {result && result.status === 'success' && (
        <>
          {/* 指标卡片 */}
          <Row gutter={16}>
            {metricCards.map((card) => {
              const Icon = card.icon;
              return (
                <Col span={6} key={card.label}>
                  <Card className="shadow-sm hover:shadow-md transition-shadow">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center shrink-0">
                        <Icon className={`w-5 h-5 ${card.color}`} />
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">{card.label}</div>
                        <div className={`text-xl font-bold ${card.color}`}>{card.value}</div>
                        <div className="text-[10px] text-gray-400 mt-0.5">{card.desc}</div>
                      </div>
                    </div>
                  </Card>
                </Col>
              );
            })}
          </Row>

          {/* 补充指标 */}
          <Card className="shadow-sm" size="small">
            <div className="flex flex-wrap gap-6">
              <Statistic title="IC 标准差" value={result.metrics.ic_std.toFixed(4)} />
              <Statistic title="十分位单调性" value={`${(result.metrics.monotonicity * 100).toFixed(0)}%`} />
              <Statistic title="Decile Rank IC" value={result.metrics.decile_rank_ic.toFixed(4)} />
              <Statistic title="T统计量" value={result.metrics.t_stat?.toFixed(2) ?? '-'} />
              <Statistic title="IC vs 随机" value={result.metrics.ic_vs_random?.toFixed(4) ?? '-'} />
              <Statistic title="回测天数" value={result.metrics.n_dates} />
              <Statistic title="失败天数" value={result.errors.length} />
              <Statistic title="平均Top十分位" value={`${(result.metrics.avg_top_decile * 100).toFixed(2)}%`} />
              <Statistic title="平均Bottom十分位" value={`${(result.metrics.avg_bottom_decile * 100).toFixed(2)}%`} />
            </div>
          </Card>

          {/* 增强指标 */}
          <Card className="shadow-sm" size="small" title="增强评估指标">
            <div className="flex flex-wrap gap-6">
              <Statistic
                title="年化Sharpe"
                value={result.metrics.sharpe_ls?.toFixed(2) ?? '-'}
                valueStyle={{ color: (result.metrics.sharpe_ls ?? 0) > 1 ? '#16a34a' : (result.metrics.sharpe_ls ?? 0) > 0 ? '#ca8a04' : '#dc2626' }}
              />
              <Statistic
                title="最大回撤"
                value={result.metrics.max_drawdown_ls != null ? `${(result.metrics.max_drawdown_ls * 100).toFixed(2)}%` : '-'}
                valueStyle={{ color: (result.metrics.max_drawdown_ls ?? 0) < 0.2 ? '#16a34a' : '#dc2626' }}
              />
              <Statistic
                title="换手率"
                value={result.metrics.turnover_mean != null ? `${(result.metrics.turnover_mean * 100).toFixed(0)}%` : '-'}
              />
              <Statistic
                title="上涨捕捉"
                value={result.metrics.up_capture?.toFixed(4) ?? '-'}
                valueStyle={{ color: (result.metrics.up_capture ?? 0) > 0 ? '#ef4444' : '#22c55e' }}
              />
              <Statistic
                title="下跌捕捉"
                value={result.metrics.down_capture?.toFixed(4) ?? '-'}
                valueStyle={{ color: (result.metrics.down_capture ?? 0) > 0 ? '#ef4444' : '#22c55e' }}
              />
            </div>
          </Card>

          {/* 图表 */}
          <Row gutter={16}>
            <Col span={14}>
              <Card title="IC 时间序列" className="shadow-sm" size="small">
                {icChartOption && (
                  <ReactECharts option={icChartOption} style={{ height: 300 }} />
                )}
              </Card>
            </Col>
            <Col span={10}>
              <Card title="十分位平均收益" className="shadow-sm" size="small">
                {decileChartOption && (
                  <ReactECharts option={decileChartOption} style={{ height: 300 }} />
                )}
              </Card>
            </Col>
          </Row>

          {/* 增强图表 */}
          <Row gutter={16}>
            <Col span={12}>
              <Card title="累积IC曲线" className="shadow-sm" size="small">
                {cumulativeICOption && (
                  <ReactECharts option={cumulativeICOption} style={{ height: 280 }} />
                )}
              </Card>
            </Col>
            <Col span={12}>
              <Card title="多空净值曲线" className="shadow-sm" size="small">
                {lsEquityOption && (
                  <ReactECharts option={lsEquityOption} style={{ height: 280 }} />
                )}
              </Card>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={24}>
              <Card title="月度IC分布" className="shadow-sm" size="small">
                {monthlyICOption && (
                  <ReactECharts option={monthlyICOption} style={{ height: 250 }} />
                )}
              </Card>
            </Col>
          </Row>

          {/* 逐日明细 */}
          <Card title="逐日回测明细" className="shadow-sm" size="small">
            <Table
              dataSource={result.per_day}
              columns={columns}
              rowKey="date"
              size="small"
              pagination={{ pageSize: 15, showTotal: (total) => `共 ${total} 天` }}
              scroll={{ x: 700 }}
            />
          </Card>

          {/* 错误列表 */}
          {result.errors.length > 0 && (
            <Card title={`失败日期 (${result.errors.length})`} className="shadow-sm" size="small">
              <Table
                dataSource={result.errors}
                columns={[
                  { title: '日期', dataIndex: 'date', key: 'date' },
                  { title: '错误信息', dataIndex: 'error', key: 'error' },
                ]}
                rowKey="date"
                size="small"
                pagination={false}
              />
            </Card>
          )}
        </>
      )}

      {/* 回测历史 */}
      {selectedModelId && history.length > 0 && (
        <Card title="回测历史" className="shadow-sm" size="small"
          extra={<Text className="text-xs text-gray-400">共 {history.length} 条记录</Text>}
        >
          <Table
            dataSource={history}
            rowKey="run_id"
            size="small"
            pagination={false}
            scroll={{ x: 600 }}
            rowClassName={(record) => record.run_id === activeRunId ? 'bg-blue-50' : ''}
            onRow={(record) => ({
              onClick: () => loadDetail(selectedModelId, record.run_id),
              style: { cursor: 'pointer' },
            })}
            columns={[
              {
                title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160,
                render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
              },
              {
                title: '日期范围', key: 'range', width: 200,
                render: (_: any, r: any) => r.date_range?.length === 2
                  ? `${r.date_range[0]} ~ ${r.date_range[1]}` : '-',
              },
              { title: '天数', dataIndex: 'n_dates', key: 'n_dates', width: 60 },
              {
                title: 'IC均值', key: 'ic', width: 90,
                render: (_: any, r: any) => {
                  const ic = r.metrics?.ic_mean;
                  return ic != null ? (
                    <span style={{ color: ic > 0 ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                      {ic.toFixed(4)}
                    </span>
                  ) : '-';
                },
              },
              {
                title: 'IC_IR', key: 'icir', width: 70,
                render: (_: any, r: any) => r.metrics?.ic_ir?.toFixed(2) ?? '-',
              },
              {
                title: '命中率', key: 'hit', width: 70,
                render: (_: any, r: any) => {
                  const hr = r.metrics?.hit_rate;
                  return hr != null ? `${(hr * 100).toFixed(0)}%` : '-';
                },
              },
              {
                title: 'T+10', key: 'horizon', width: 50,
                render: (_: any, r: any) => `T+${r.horizon || 10}`,
              },
              {
                title: '', key: 'actions', width: 40,
                render: (_: any, r: any) => (
                  <Popconfirm title="确定删除？" onConfirm={(e) => { e?.stopPropagation(); deleteHistoryItem(r.run_id); }}>
                    <Button type="text" size="small" danger icon={<Trash2 className="w-3 h-3" />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                ),
              },
            ]}
          />
        </Card>
      )}

      {/* 空状态 */}
      {!loading && !result && history.length === 0 && (
        <Card className="shadow-sm">
          <Empty
            description="选择模型和日期范围，点击「开始回测」评估模型预测质量"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      )}
    </div>
  );
};
