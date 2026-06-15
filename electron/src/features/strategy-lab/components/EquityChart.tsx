/**
 * EquityChart — strategy net value + benchmark + drawdown overlay.
 *
 * Reusable component:
 *   <EquityChart equity={result.equity} height={280} />
 *
 * Renders three series sharing one X-axis:
 *   - "策略" — strategy normalized to start = 1.0 (left Y axis)
 *   - "基准" — benchmark normalized to start = 1.0 (left Y axis, hidden if no data)
 *   - "回撤" — drawdown shaded area below baseline (right Y axis, % scale)
 */

import React, { useMemo } from 'react';
import {
  ComposedChart,
  Area,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { Empty } from 'antd';
import type { StrategyLabEquityPoint } from '../types';

interface Props {
  equity: StrategyLabEquityPoint[];
  height?: number;
  /** Optional baseline series — rendered as dashed orange line for vs comparison. */
  prevEquity?: StrategyLabEquityPoint[] | null;
  prevLabel?: string;
}

interface ChartRow {
  date: string;
  strategy: number;
  benchmark: number | null;
  drawdown: number;
  prev: number | null;
}

const buildChartData = (
  equity: StrategyLabEquityPoint[],
  prev?: StrategyLabEquityPoint[] | null,
): ChartRow[] => {
  if (!equity.length) return [];
  const base = equity[0]?.value ?? 1;
  const benchBase = equity[0]?.benchmark ?? null;

  // Normalize prev curve and build a date-indexed map for alignment.
  const prevMap = new Map<string, number>();
  if (prev && prev.length > 0) {
    const prevBase = prev[0]?.value ?? 1;
    for (const p of prev) {
      if (prevBase) prevMap.set(p.date, p.value / prevBase);
    }
  }

  let peak = -Infinity;
  return equity.map((p) => {
    const norm = base ? p.value / base : 0;
    if (norm > peak) peak = norm;
    const dd = peak > 0 ? norm / peak - 1 : 0;
    return {
      date: p.date,
      strategy: norm,
      benchmark: benchBase && p.benchmark ? p.benchmark / benchBase : null,
      drawdown: dd,
      prev: prevMap.has(p.date) ? prevMap.get(p.date)! : null,
    };
  });
};

export const EquityChart: React.FC<Props> = ({ equity, height = 280, prevEquity, prevLabel = '上一版' }) => {
  const data = useMemo(() => buildChartData(equity, prevEquity), [equity, prevEquity]);
  const hasBench = useMemo(() => data.some((d) => d.benchmark !== null), [data]);
  const hasPrev = useMemo(() => data.some((d) => d.prev !== null), [data]);

  if (data.length === 0) {
    return <Empty description="无净值数据" />;
  }

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 12, right: 24, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={20} />
          <YAxis
            yAxisId="value"
            tick={{ fontSize: 10 }}
            domain={['auto', 'auto']}
            tickFormatter={(v: number) => v.toFixed(2)}
          />
          <YAxis
            yAxisId="dd"
            orientation="right"
            tick={{ fontSize: 10 }}
            domain={[(dataMin: number) => Math.min(dataMin, -0.05), 0]}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          />
          <Tooltip
            formatter={(value: number, name: string) => {
              if (name === '回撤') return [`${(value * 100).toFixed(2)}%`, name];
              return [value.toFixed(4), name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area
            yAxisId="dd"
            type="monotone"
            dataKey="drawdown"
            name="回撤"
            stroke="#cf1322"
            fill="#cf132222"
            isAnimationActive={false}
          />
          <Area
            yAxisId="value"
            type="monotone"
            dataKey="strategy"
            name="策略"
            stroke="#1677ff"
            fill="#1677ff22"
            isAnimationActive={false}
          />
          {hasBench && (
            <Line
              yAxisId="value"
              type="monotone"
              dataKey="benchmark"
              name="基准"
              stroke="#888"
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={false}
            />
          )}
          {hasPrev && (
            <Line
              yAxisId="value"
              type="monotone"
              dataKey="prev"
              name={prevLabel}
              stroke="#fa8c16"
              strokeDasharray="6 4"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EquityChart;
