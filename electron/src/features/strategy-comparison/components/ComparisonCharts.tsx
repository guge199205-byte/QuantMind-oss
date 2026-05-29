/**
 * 策略对比图表组件
 * Strategy Comparison Charts
 *
 * 可视化展示策略对比数据
 *
 * @author QuantMind Team
 * @date 2025-12-02
 */

import React, { useMemo } from 'react';
import { Card, Row, Col, Empty } from 'antd';
import {
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts';
import type { StrategyComparisonItem } from '../../../shared/types/strategyComparison';

export interface ComparisonChartsProps {
  /** 对比策略列表 */
  strategies: StrategyComparisonItem[];
}

// 颜色主题
const CHART_COLORS = [
  '#1890ff', // 蓝色
  '#52c41a', // 绿色
  '#faad14', // 橙色
  '#f5222d', // 红色
  '#722ed1', // 紫色
];

/**
 * 策略对比图表组件
 */
export const ComparisonCharts: React.FC<ComparisonChartsProps> = ({ strategies }) => {
  // 收益曲线数据
  const equityCurveData = useMemo(() => {
    if (strategies.length === 0) return [];

    // 获取所有日期的并集
    const allDates = new Set<string>();
    strategies.forEach(s => {
      s.equity_curve.dates.forEach(date => allDates.add(date));
    });

    const sortedDates = Array.from(allDates).sort();

    // 构建数据
    return sortedDates.map(date => {
      const dataPoint: any = { date };

      strategies.forEach(strategy => {
        const dateIndex = strategy.equity_curve.dates.indexOf(date);
        if (dateIndex >= 0) {
          dataPoint[strategy.strategy_name] = strategy.equity_curve.returns[dateIndex];
        }
      });

      return dataPoint;
    });
  }, [strategies]);

  // 风险收益散点图数据
  const riskReturnData = useMemo(() => {
    return strategies.map((strategy, index) => ({
      name: strategy.strategy_name,
      risk: Math.abs(strategy.performance.max_drawdown),
      return: strategy.performance.annual_return,
      sharpe: strategy.performance.sharpe_ratio,
      color: CHART_COLORS[index % CHART_COLORS.length],
    }));
  }, [strategies]);

  // 雷达图数据
  const radarData = useMemo(() => {
    // 标准化数据到0-100范围
    const normalize = (value: number, min: number, max: number) => {
      if (max === min) return 50;
      return ((value - min) / (max - min)) * 100;
    };

    // 获取各指标的最大最小值
    const returns = strategies.map(s => s.performance.annual_return);
    const drawdowns = strategies.map(s => Math.abs(s.performance.max_drawdown));
    const sharpes = strategies.map(s => s.performance.sharpe_ratio);
    const winRates = strategies.map(s => s.trading_stats.win_rate);
    const volatilities = strategies.map(s => s.performance.volatility);

    const indicators = [
      {
        subject: '年化收益',
        fullMark: 100,
        ...strategies.reduce((acc, strategy, index) => {
          acc[strategy.strategy_name] = normalize(
            strategy.performance.annual_return,
            Math.min(...returns),
            Math.max(...returns)
          );
          return acc;
        }, {} as Record<string, number>),
      },
      {
        subject: '风险控制',
        fullMark: 100,
        ...strategies.reduce((acc, strategy, index) => {
          // 回撤越小越好，所以反转
          acc[strategy.strategy_name] = 100 - normalize(
            Math.abs(strategy.performance.max_drawdown),
            Math.min(...drawdowns),
            Math.max(...drawdowns)
          );
          return acc;
        }, {} as Record<string, number>),
      },
      {
        subject: '夏普比率',
        fullMark: 100,
        ...strategies.reduce((acc, strategy, index) => {
          acc[strategy.strategy_name] = normalize(
            strategy.performance.sharpe_ratio,
            Math.min(...sharpes),
            Math.max(...sharpes)
          );
          return acc;
        }, {} as Record<string, number>),
      },
      {
        subject: '胜率',
        fullMark: 100,
        ...strategies.reduce((acc, strategy, index) => {
          acc[strategy.strategy_name] = normalize(
            strategy.trading_stats.win_rate,
            Math.min(...winRates),
            Math.max(...winRates)
          );
          return acc;
        }, {} as Record<string, number>),
      },
      {
        subject: '稳定性',
        fullMark: 100,
        ...strategies.reduce((acc, strategy, index) => {
          // 波动率越小越好，所以反转
          acc[strategy.strategy_name] = 100 - normalize(
            strategy.performance.volatility,
            Math.min(...volatilities),
            Math.max(...volatilities)
          );
          return acc;
        }, {} as Record<string, number>),
      },
    ];

    return indicators;
  }, [strategies]);

  // 自定义Tooltip
  const CustomTooltip = ({ active, payload, label }: TooltipProps<any, any>) => {
    if (active && payload && payload.length) {
      return (
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            padding: '10px',
            border: '1px solid #d9d9d9',
            borderRadius: '4px',
          }}
        >
          <p style={{ margin: 0, fontWeight: 500 }}>{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ margin: '4px 0', color: entry.color }}>
              {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
              {entry.dataKey !== 'date' && '%'}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  if (strategies.length === 0) {
    return <Empty description="请选择至少2个策略进行对比" />;
  }

  return (
    <div className="comparison-charts">
      <Row gutter={[16, 16]}>
        {/* 收益曲线图 */}
        <Col span={24}>
          <Card title="📈 累计收益曲线对比" variant="borderless">
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={equityCurveData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  style={{ fontSize: 12 }}
                />
                <YAxis
                  label={{ value: '累计收益率(%)', angle: -90, position: 'insideLeft' }}
                  style={{ fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                {strategies.map((strategy, index) => (
                  <Line
                    key={strategy.strategy_id}
                    type="monotone"
                    dataKey={strategy.strategy_name}
                    stroke={CHART_COLORS[index % CHART_COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 16, fontSize: 12, color: '#8c8c8c', textAlign: 'center' }}>
              该图展示了各策略的累计收益曲线，可直观对比不同策略的收益表现
            </div>
          </Card>
        </Col>

        {/* 风险收益散点图 */}
        <Col xs={24} lg={12}>
          <Card title="🎯 风险收益散点图" variant="borderless">
            <ResponsiveContainer width="100%" height={350}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="risk"
                  name="最大回撤"
                  label={{ value: '最大回撤(%)', position: 'insideBottom', offset: -5 }}
                  style={{ fontSize: 12 }}
                />
                <YAxis
                  type="number"
                  dataKey="return"
                  name="年化收益"
                  label={{ value: '年化收益率(%)', angle: -90, position: 'insideLeft' }}
                  style={{ fontSize: 12 }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div
                          style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            padding: '10px',
                            border: '1px solid #d9d9d9',
                            borderRadius: '4px',
                          }}
                        >
                          <p style={{ margin: 0, fontWeight: 500 }}>{data.name}</p>
                          <p style={{ margin: '4px 0', color: '#52c41a' }}>
                            年化收益: {data.return.toFixed(2)}%
                          </p>
                          <p style={{ margin: '4px 0', color: '#f5222d' }}>
                            最大回撤: {data.risk.toFixed(2)}%
                          </p>
                          <p style={{ margin: '4px 0', color: '#1890ff' }}>
                            夏普比率: {data.sharpe.toFixed(2)}
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Legend />
                {riskReturnData.map((entry, index) => (
                  <Scatter
                    key={entry.name}
                    name={entry.name}
                    data={[entry]}
                    fill={entry.color}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 16, fontSize: 12, color: '#8c8c8c', textAlign: 'center' }}>
              左上角表示低风险高收益（理想区域），右下角表示高风险低收益
            </div>
          </Card>
        </Col>

        {/* 雷达图 */}
        <Col xs={24} lg={12}>
          <Card title="🕸️ 综合能力雷达图" variant="borderless">
            <ResponsiveContainer width="100%" height={350}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="subject" style={{ fontSize: 12 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} style={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                {strategies.map((strategy, index) => (
                  <Radar
                    key={strategy.strategy_id}
                    name={strategy.strategy_name}
                    dataKey={strategy.strategy_name}
                    stroke={CHART_COLORS[index % CHART_COLORS.length]}
                    fill={CHART_COLORS[index % CHART_COLORS.length]}
                    fillOpacity={0.3}
                  />
                ))}
              </RadarChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 16, fontSize: 12, color: '#8c8c8c', textAlign: 'center' }}>
              雷达图面积越大，策略综合能力越强
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ComparisonCharts;
