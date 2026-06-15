import React, { useMemo, useState } from 'react';
import { Tooltip, Typography } from 'antd';
import clsx from 'clsx';
import type { ScoreDistribution } from '../../services/modelTrainingService';

const { Text } = Typography;

interface Props {
  dist: ScoreDistribution;
}

const fmt = (n: number | undefined | null, digits = 4): string => {
  if (n === undefined || n === null || !Number.isFinite(n)) return '—';
  return n.toFixed(digits);
};

const fmtPct = (n: number | undefined | null): string => {
  if (n === undefined || n === null || !Number.isFinite(n)) return '—';
  return `${n.toFixed(1)}%`;
};

export const ScoreDistributionPanel: React.FC<Props> = ({ dist }) => {
  const [hover, setHover] = useState<number | null>(null);

  const W = 480;
  const H = 56;
  const PL = 4;
  const PR = 4;
  const PT = 4;
  const PB = 4;
  const IW = W - PL - PR;
  const IH = H - PT - PB;

  const maxCount = useMemo(() => {
    return dist.histogram.reduce((m, b) => (b.count > m ? b.count : m), 0) || 1;
  }, [dist.histogram]);

  const lo = dist.min;
  const hi = dist.max;
  const span = hi - lo || 1;
  const zeroX = lo < 0 && hi > 0 ? PL + ((0 - lo) / span) * IW : null;
  const barW = IW / Math.max(dist.histogram.length, 1);

  const bucketColor = (b: { x0: number; x1: number }): string => {
    if (b.x0 >= 0) return '#34d399'; // emerald-400
    if (b.x1 <= 0) return '#fb7185'; // rose-400
    return '#cbd5e1'; // slate-300
  };

  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <Text className="text-[10px] text-slate-400 font-black uppercase tracking-wide">分数分布</Text>
        <Text className="text-[10px] text-slate-400 font-mono">N={dist.count.toLocaleString()}</Text>
      </div>

      {/* 4 张紧凑统计卡 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div className="rounded-xl bg-emerald-50 border border-emerald-100 px-3 py-2">
          <div className="text-[10px] text-emerald-600 font-black uppercase">正分占比</div>
          <div className="flex items-baseline gap-1 mt-0.5">
            <span className="text-base font-black text-emerald-700 font-mono">{fmtPct(dist.positive_pct)}</span>
            <span className="text-[10px] text-emerald-500 font-mono">{dist.positive_count.toLocaleString()}</span>
          </div>
        </div>
        <div className="rounded-xl bg-rose-50 border border-rose-100 px-3 py-2">
          <div className="text-[10px] text-rose-600 font-black uppercase">负分占比</div>
          <div className="flex items-baseline gap-1 mt-0.5">
            <span className="text-base font-black text-rose-700 font-mono">{fmtPct(dist.negative_pct)}</span>
            <span className="text-[10px] text-rose-500 font-mono">{dist.negative_count.toLocaleString()}</span>
          </div>
        </div>
        <div className="rounded-xl bg-white border border-slate-100 px-3 py-2">
          <div className="text-[10px] text-slate-500 font-black uppercase">中位数</div>
          <div className="text-base font-black text-slate-800 font-mono mt-0.5">{fmt(dist.median)}</div>
        </div>
        <div className="rounded-xl bg-white border border-slate-100 px-3 py-2">
          <Tooltip title="Top 10% 股票的分数门槛">
            <div className="text-[10px] text-slate-500 font-black uppercase cursor-help">Top10% 门槛</div>
          </Tooltip>
          <div className="text-base font-black text-slate-800 font-mono mt-0.5">{fmt(dist.p90)}</div>
        </div>
      </div>

      {/* 直方图 */}
      <div className="rounded-xl bg-white border border-slate-100 px-3 py-2">
        <div className="flex items-center justify-between mb-1">
          <Text className="text-[10px] text-slate-400 font-mono">{fmt(lo)}</Text>
          <Text className="text-[10px] text-slate-400 font-black">分布直方图（20 桶）</Text>
          <Text className="text-[10px] text-slate-400 font-mono">{fmt(hi)}</Text>
        </div>
        <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
          {dist.histogram.map((b, i) => {
            const h = (b.count / maxCount) * IH;
            const x = PL + i * barW;
            const y = PT + (IH - h);
            const active = hover === i;
            return (
              <Tooltip
                key={i}
                title={
                  <div className="font-mono text-[11px]">
                    <div>区间: [{fmt(b.x0)} , {fmt(b.x1)}]</div>
                    <div>数量: {b.count.toLocaleString()} ({((b.count / dist.count) * 100).toFixed(1)}%)</div>
                  </div>
                }
              >
                <rect
                  x={x + 0.5}
                  y={y}
                  width={Math.max(barW - 1, 0.5)}
                  height={h}
                  fill={bucketColor(b)}
                  opacity={active ? 1 : 0.85}
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                  style={{ cursor: 'pointer', transition: 'opacity 120ms' }}
                />
              </Tooltip>
            );
          })}
          {/* 0 分线 */}
          {zeroX !== null && (
            <line
              x1={zeroX}
              x2={zeroX}
              y1={PT - 1}
              y2={H - PB + 1}
              stroke="#64748b"
              strokeWidth={1}
              strokeDasharray="2,2"
            />
          )}
        </svg>
      </div>

      {/* 分位点 */}
      <div className="grid grid-cols-5 gap-1.5">
        {[
          { label: 'P10', value: dist.p10 },
          { label: 'P25', value: dist.p25 },
          { label: '中位', value: dist.median },
          { label: 'P75', value: dist.p75 },
          { label: 'P90', value: dist.p90 },
        ].map((pt) => (
          <div
            key={pt.label}
            className={clsx(
              'rounded-lg border px-2 py-1 text-center',
              pt.value >= 0 ? 'border-emerald-100 bg-emerald-50/40' : 'border-rose-100 bg-rose-50/40',
            )}
          >
            <div className="text-[9px] text-slate-500 font-black uppercase">{pt.label}</div>
            <div className={clsx('text-[11px] font-black font-mono', pt.value >= 0 ? 'text-emerald-700' : 'text-rose-700')}>
              {fmt(pt.value)}
            </div>
          </div>
        ))}
      </div>

      {/* 辅助行：均值/标准差/极值 */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-500 font-mono">
        <span>均值 <span className="text-slate-800 font-black">{fmt(dist.mean)}</span></span>
        <span>σ <span className="text-slate-800 font-black">{fmt(dist.stdev)}</span></span>
        <span>极小 <span className="text-rose-700 font-black">{fmt(dist.min)}</span></span>
        <span>极大 <span className="text-emerald-700 font-black">{fmt(dist.max)}</span></span>
        {dist.zero_count > 0 && (
          <span>零分 <span className="text-slate-800 font-black">{dist.zero_count.toLocaleString()}</span></span>
        )}
      </div>
    </div>
  );
};

export default ScoreDistributionPanel;
