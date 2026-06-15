import React, { useMemo } from 'react';
import { Empty, Table } from 'antd';
import type { StrategyLabEquityPoint } from '../types';

interface Props {
  equity: StrategyLabEquityPoint[];
}

interface YearStat {
  year: string;
  start_value: number;
  end_value: number;
  ret: number;
  benchmark_ret: number | null;
  alpha: number | null;
  max_dd: number;
  n_days: number;
}

function buildYearlyStats(equity: StrategyLabEquityPoint[]): YearStat[] {
  if (!equity?.length) return [];
  const buckets = new Map<string, StrategyLabEquityPoint[]>();
  for (const p of equity) {
    const yr = p.date.slice(0, 4);
    if (!buckets.has(yr)) buckets.set(yr, []);
    buckets.get(yr)!.push(p);
  }
  const out: YearStat[] = [];
  for (const [year, points] of Array.from(buckets.entries()).sort()) {
    if (!points.length) continue;
    const start = points[0];
    const end = points[points.length - 1];
    const ret = start.value ? end.value / start.value - 1 : 0;
    let benchRet: number | null = null;
    if (start.benchmark != null && end.benchmark != null && start.benchmark) {
      benchRet = end.benchmark / start.benchmark - 1;
    }
    let peak = start.value;
    let maxDd = 0;
    for (const p of points) {
      if (p.value > peak) peak = p.value;
      const dd = peak > 0 ? p.value / peak - 1 : 0;
      if (dd < maxDd) maxDd = dd;
    }
    out.push({
      year,
      start_value: start.value,
      end_value: end.value,
      ret,
      benchmark_ret: benchRet,
      alpha: benchRet === null ? null : ret - benchRet,
      max_dd: maxDd,
      n_days: points.length,
    });
  }
  return out;
}

const fmtPct = (v: number | null | undefined) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  const pct = v * 100;
  const color = pct > 0 ? '#cf1322' : pct < 0 ? '#3f8600' : '#888';
  return <span style={{ color }}>{pct.toFixed(2)}%</span>;
};

export const YearlyStats: React.FC<Props> = ({ equity }) => {
  const rows = useMemo(() => buildYearlyStats(equity), [equity]);
  if (!rows.length) return <Empty description="数据不足" />;
  return (
    <Table
      size="small"
      rowKey="year"
      pagination={false}
      dataSource={rows}
      columns={[
        { title: '年度', dataIndex: 'year', width: 80 },
        { title: '收益', dataIndex: 'ret', width: 90, render: fmtPct },
        { title: '基准', dataIndex: 'benchmark_ret', width: 90, render: fmtPct },
        { title: '超额', dataIndex: 'alpha', width: 90, render: fmtPct },
        { title: '最大回撤', dataIndex: 'max_dd', width: 100, render: fmtPct },
        { title: '交易日数', dataIndex: 'n_days', width: 80 },
      ]}
    />
  );
};

export default YearlyStats;
