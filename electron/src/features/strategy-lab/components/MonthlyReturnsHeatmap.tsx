/**
 * MonthlyReturnsHeatmap — small calendar grid of strategy monthly returns.
 *
 * Useful for spotting "strategy actually loses every Aug" style patterns.
 * Pure presentational — pass equity array, we group by year/month.
 */

import React, { useMemo } from 'react';
import { Empty, Tooltip } from 'antd';
import type { StrategyLabEquityPoint } from '../types';

interface Props {
  equity: StrategyLabEquityPoint[];
}

interface MonthCell {
  year: number;
  month: number; // 1..12
  ret: number;
}

const computeMonthly = (equity: StrategyLabEquityPoint[]): MonthCell[] => {
  if (equity.length < 2) return [];
  // Group by YYYY-MM, take last value of each group, then % change vs previous group's last
  const buckets = new Map<string, number>();
  for (const p of equity) {
    const key = p.date.slice(0, 7); // YYYY-MM
    buckets.set(key, p.value);
  }
  const sorted = Array.from(buckets.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  const out: MonthCell[] = [];
  for (let i = 1; i < sorted.length; i++) {
    const [key, value] = sorted[i];
    const prev = sorted[i - 1][1];
    if (!prev) continue;
    const ret = value / prev - 1;
    const [yStr, mStr] = key.split('-');
    out.push({ year: Number(yStr), month: Number(mStr), ret });
  }
  return out;
};

const colorFor = (ret: number): string => {
  if (Math.abs(ret) < 1e-6) return '#f5f5f5';
  const intensity = Math.min(Math.abs(ret) / 0.10, 1); // cap at ±10%
  if (ret > 0) {
    const alpha = (0.15 + intensity * 0.55).toFixed(2);
    return `rgba(63, 134, 0, ${alpha})`;
  }
  const alpha = (0.15 + intensity * 0.55).toFixed(2);
  return `rgba(207, 19, 34, ${alpha})`;
};

export const MonthlyReturnsHeatmap: React.FC<Props> = ({ equity }) => {
  const cells = useMemo(() => computeMonthly(equity), [equity]);
  if (cells.length === 0) {
    return <Empty description="样本不足以计算月度收益" />;
  }

  const years = Array.from(new Set(cells.map((c) => c.year))).sort();
  const byYear = new Map<number, Map<number, number>>();
  for (const c of cells) {
    if (!byYear.has(c.year)) byYear.set(c.year, new Map());
    byYear.get(c.year)!.set(c.month, c.ret);
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'separate', borderSpacing: 4, fontSize: 11 }}>
        <thead>
          <tr>
            <th style={{ padding: 4, textAlign: 'right', color: '#666' }}>年/月</th>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <th key={m} style={{ padding: 4, color: '#666', minWidth: 36, textAlign: 'center' }}>
                {m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map((y) => (
            <tr key={y}>
              <td style={{ padding: 4, textAlign: 'right', color: '#666' }}>{y}</td>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
                const ret = byYear.get(y)?.get(m);
                if (ret === undefined) {
                  return (
                    <td
                      key={m}
                      style={{
                        background: 'transparent',
                        border: '1px dashed #eee',
                        borderRadius: 4,
                        height: 28,
                      }}
                    />
                  );
                }
                return (
                  <td key={m} style={{ padding: 0 }}>
                    <Tooltip title={`${y}-${String(m).padStart(2, '0')}: ${(ret * 100).toFixed(2)}%`}>
                      <div
                        style={{
                          background: colorFor(ret),
                          borderRadius: 4,
                          padding: '4px 6px',
                          textAlign: 'center',
                          fontWeight: 500,
                          color: Math.abs(ret) > 0.05 ? '#fff' : '#333',
                          minWidth: 36,
                        }}
                      >
                        {(ret * 100).toFixed(1)}
                      </div>
                    </Tooltip>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MonthlyReturnsHeatmap;
