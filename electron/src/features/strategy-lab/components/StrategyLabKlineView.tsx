import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  createChart,
  CrosshairMode,
  CandlestickSeries,
  createSeriesMarkers,
  IChartApi,
  ISeriesApi,
  Time,
  IPriceLine,
} from 'lightweight-charts';
import { Empty, Select, Space, Spin, Tag, Typography, Button, Tooltip, message, Popconfirm } from 'antd';
import { EditOutlined, ClearOutlined } from '@ant-design/icons';
import axios from 'axios';
import { authService } from '../../auth/services/authService';
import { SERVICE_ENDPOINTS } from '../../../config/services';
import type { StrategyLabRunResult, StrategyLabTradeRecord } from '../types';

const { Text } = Typography;

interface KlineItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface KlineResponse {
  success: boolean;
  data: { items: KlineItem[]; source_used?: string };
}

const baseURL =
  (import.meta as any).env?.VITE_USER_API_URL || SERVICE_ENDPOINTS.USER_SERVICE;

/** Convert SDK symbol (sh600519 / 00700.HK / AAPL) → kline API format. */
function toKlineParams(sdkSymbol: string): { symbol: string; market: 'A' | 'HK' | 'US' } {
  const s = sdkSymbol.trim();
  const lower = s.toLowerCase();
  if (lower.startsWith('sh') || lower.startsWith('sz') || lower.startsWith('bj')) {
    const prefix = lower.slice(0, 2).toUpperCase();
    const code = s.slice(2);
    return { symbol: `${code}.${prefix}`, market: 'A' };
  }
  if (s.endsWith('.HK') || /^\d{4,5}$/.test(s)) {
    return { symbol: s.endsWith('.HK') ? s : s, market: 'HK' };
  }
  // Already in 600519.SH style
  if (/\.(SH|SZ|BJ)$/i.test(s)) return { symbol: s.toUpperCase(), market: 'A' };
  return { symbol: s.toUpperCase(), market: 'US' };
}

async function fetchKline(symbol: string, market: 'A' | 'HK' | 'US', start: string, end: string): Promise<KlineItem[]> {
  const token = authService.getAccessToken();
  // Cap range to 3 yrs but also pad ±30 days so the latest trade marker isn't clipped at the edge.
  const days = Math.max(
    30,
    Math.min(750, Math.ceil((new Date(end).getTime() - new Date(start).getTime()) / 86_400_000) + 30),
  );
  try {
    const resp = await axios.get<KlineResponse>(`${baseURL}/market/kline`, {
      // Pass explicit start/end so the API returns data from the *backtest*
      // window — not just the most-recent N days from today (which would put
      // the chart in a different time range than the markers).
      params: { symbol, market, period: 'daily', start, end, days },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      timeout: 30_000,
    });
    return resp.data.data?.items || [];
  } catch {
    return [];
  }
}

interface Props {
  result: StrategyLabRunResult;
  onMarkerClick?: (trade: StrategyLabTradeRecord) => void;
  height?: number;
  /** Day 17: persisted hand-drawn lines, keyed by user-supplied name. */
  drawnLines?: Record<string, number>;
  /** Day 17: callback when user adds/removes a hand-drawn line on the chart. */
  onDrawnLinesChange?: (next: Record<string, number>) => void;
}

export const StrategyLabKlineView: React.FC<Props> = ({
  result,
  onMarkerClick,
  height = 360,
  drawnLines,
  onDrawnLinesChange,
}) => {
  // Distinct symbols from trades
  const symbols = useMemo(() => {
    const set = new Set<string>();
    for (const t of result.trades || []) set.add(t.symbol);
    // Also include explicit overlay symbols
    for (const m of result.overlays?.markers || []) if (m.symbol) set.add(m.symbol);
    for (const ln of result.overlays?.lines || []) if (ln.symbol) set.add(ln.symbol);
    if (!set.size) {
      // fallback to config.universe (single string list) so chart still renders
      const universe = (result.config as any)?.universe;
      if (Array.isArray(universe) && universe[0]) set.add(String(universe[0]));
      else if (typeof universe === 'string' && universe) set.add(universe);
    }
    return Array.from(set);
  }, [result]);

  const [selected, setSelected] = useState<string | null>(symbols[0] || null);
  // When a fresh backtest produces a different symbol set, the previous
  // `selected` may no longer exist — fall back to the first available symbol
  // so the chart doesn't fetch stale data outside the new date window.
  useEffect(() => {
    if (!symbols.length) {
      if (selected !== null) setSelected(null);
      return;
    }
    if (!selected || !symbols.includes(selected)) {
      setSelected(symbols[0]);
    }
  }, [symbols, selected]);

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ReturnType<typeof createSeriesMarkers> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const drawnPriceLinesRef = useRef<Map<string, IPriceLine>>(new Map());
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<KlineItem[]>([]);
  const [drawMode, setDrawMode] = useState(false);

  // chart init
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: { background: { color: '#ffffff' }, textColor: '#475569' },
      grid: { vertLines: { color: '#f1f5f9' }, horzLines: { color: '#f1f5f9' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#e2e8f0' },
      timeScale: { borderColor: '#e2e8f0', timeVisible: false },
    });
    chartRef.current = chart;
    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#10b981',
      borderUpColor: '#ef4444',
      borderDownColor: '#10b981',
      wickUpColor: '#ef4444',
      wickDownColor: '#10b981',
    });
    markersRef.current = createSeriesMarkers(candleRef.current, []);
    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      markersRef.current = null;
      priceLinesRef.current = [];
      drawnPriceLinesRef.current = new Map();
    };
  }, [height]);

  // fetch data
  useEffect(() => {
    if (!selected) return;
    const cfg = (result.config || {}) as Record<string, unknown>;
    const start = String(cfg.start || result.equity?.[0]?.date || '2026-01-05').slice(0, 10);
    const end = String(cfg.end || result.equity?.[result.equity.length - 1]?.date || '2026-06-12').slice(0, 10);
    const { symbol: apiSym, market } = toKlineParams(selected);
    let cancelled = false;
    setLoading(true);
    fetchKline(apiSym, market, start, end)
      .then((d) => {
        if (cancelled) return;
        // Filter to backtest window so markers align
        setItems(d.filter((k) => k.date >= start && k.date <= end));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [selected, result]);

  // populate candles + markers + horizontal price lines
  useEffect(() => {
    if (!candleRef.current || !chartRef.current) return;
    if (items.length) {
      candleRef.current.setData(
        items.map((k) => ({
          time: k.date as Time,
          open: k.open,
          high: k.high,
          low: k.low,
          close: k.close,
        })),
      );
    } else {
      candleRef.current.setData([]);
    }

    // Build markers from trades + overlay markers, all filtered by selected symbol
    const tradeMarkers = (result.trades || [])
      .filter((t) => t.symbol === selected)
      .map((t) => ({
        time: t.date as Time,
        position: t.direction === 'BUY' ? ('belowBar' as const) : ('aboveBar' as const),
        color: t.direction === 'BUY' ? '#ef4444' : '#10b981',
        shape: t.direction === 'BUY' ? ('arrowUp' as const) : ('arrowDown' as const),
        text: `${t.direction} @${t.price.toFixed(2)}`,
        // attach trade id for click-back
        id: `trade:${t.date}:${t.direction}`,
      }));

    const overlayMarkers = (result.overlays?.markers || [])
      .filter((m) => m.symbol === selected && m.ts)
      .map((m) => ({
        time: (m.ts as string).slice(0, 10) as Time,
        position: 'aboveBar' as const,
        color: '#6366f1',
        shape: 'circle' as const,
        text: m.text || m.type,
      }));

    const all = [...tradeMarkers, ...overlayMarkers].sort(
      (a, b) => String(a.time).localeCompare(String(b.time)),
    );
    try {
      if (markersRef.current) {
        markersRef.current.setMarkers(all as any);
      }
    } catch {
      // marker plugin not available: ignore
    }

    // Remove previous horizontal price lines
    for (const pl of priceLinesRef.current) {
      try {
        candleRef.current.removePriceLine(pl);
      } catch {
        /* noop */
      }
    }
    priceLinesRef.current = [];

    // Draw horizontal lines for overlays.lines that match symbol (latest value
    // per name kept — strategies may emit it daily)
    const lineByName = new Map<string, { value: number; name: string }>();
    for (const ln of result.overlays?.lines || []) {
      if (ln.symbol && ln.symbol !== selected) continue;
      lineByName.set(ln.name, { value: ln.value, name: ln.name });
    }
    for (const { value, name } of lineByName.values()) {
      try {
        const pl = candleRef.current.createPriceLine({
          price: value,
          color: '#6366f1',
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: name,
        });
        priceLinesRef.current.push(pl);
      } catch {
        /* noop */
      }
    }

    chartRef.current.timeScale().fitContent();
  }, [items, result, selected]);

  // Day 17: render drawn (hand-drawn) horizontal price lines
  useEffect(() => {
    if (!candleRef.current) return;
    // remove all previously drawn lines first
    for (const pl of drawnPriceLinesRef.current.values()) {
      try {
        candleRef.current.removePriceLine(pl);
      } catch {
        /* noop */
      }
    }
    drawnPriceLinesRef.current = new Map();

    const lines = drawnLines || {};
    for (const [name, value] of Object.entries(lines)) {
      if (typeof value !== 'number' || !Number.isFinite(value)) continue;
      try {
        const pl = candleRef.current.createPriceLine({
          price: value,
          color: '#fa8c16',
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: `✏ ${name}`,
        });
        drawnPriceLinesRef.current.set(name, pl);
      } catch {
        /* noop */
      }
    }
  }, [drawnLines]);

  // Day 17: click-to-add drawn line when drawMode is on
  useEffect(() => {
    if (!chartRef.current || !candleRef.current || !drawMode || !onDrawnLinesChange) return;
    const chart = chartRef.current;
    const series = candleRef.current;
    const handler = (param: any) => {
      if (!param || !param.point) return;
      const price = (series as any).coordinateToPrice?.(param.point.y);
      if (typeof price !== 'number' || !Number.isFinite(price)) return;
      const name = window.prompt('为这条线起一个名字（脚本中用 ctx.drawn_line(name) 读取）：', 'stop_loss');
      if (!name) return;
      const next = { ...(drawnLines || {}), [name]: Number(price.toFixed(4)) };
      onDrawnLinesChange(next);
      message.success(`已记录 ${name} = ${price.toFixed(2)}（重新运行回测以让脚本读取）`);
      setDrawMode(false);
    };
    chart.subscribeClick(handler);
    return () => {
      try {
        chart.unsubscribeClick(handler);
      } catch {
        /* noop */
      }
    };
  }, [drawMode, drawnLines, onDrawnLinesChange]);

  // Marker click → bubble up nearest trade by date
  useEffect(() => {
    if (!chartRef.current || !onMarkerClick) return;
    const chart = chartRef.current;
    const handler = (param: any) => {
      if (drawMode) return; // draw-mode handler owns the click
      if (!param || !param.time) return;
      const dateStr = String(param.time);
      const candidates = (result.trades || []).filter(
        (t) => t.symbol === selected && t.date === dateStr,
      );
      if (candidates.length === 1) {
        onMarkerClick(candidates[0]);
      } else if (candidates.length > 1) {
        // Pick BUY first, fall back to first
        onMarkerClick(candidates.find((c) => c.direction === 'BUY') || candidates[0]);
      }
    };
    chart.subscribeClick(handler);
    return () => {
      try {
        chart.unsubscribeClick(handler);
      } catch {
        /* noop */
      }
    };
  }, [onMarkerClick, result, selected, drawMode]);

  if (!symbols.length) {
    return <Empty description="本次回测无成交，K线无可绘制标的" />;
  }

  return (
    <div>
      <Space style={{ marginBottom: 8 }} size="middle" wrap>
        <Text strong>K 线标的</Text>
        <Select
          size="small"
          style={{ minWidth: 160 }}
          value={selected || undefined}
          onChange={(v) => setSelected(v)}
          options={symbols.map((s) => ({ value: s, label: s }))}
        />
        <Tag color="default">▲ 买入</Tag>
        <Tag color="default">▼ 卖出</Tag>
        {result.overlays?.lines?.length ? <Tag color="purple">虚线 = ctx.plot_line</Tag> : null}
        {onDrawnLinesChange && (
          <>
            <Tooltip title="开启后点击图表任意位置即可记一条横线，脚本中 ctx.drawn_line('name') 读取">
              <Button
                size="small"
                type={drawMode ? 'primary' : 'default'}
                icon={<EditOutlined />}
                onClick={() => setDrawMode((v) => !v)}
              >
                {drawMode ? '点击图表选择价位…' : '+ 画线'}
              </Button>
            </Tooltip>
            {drawnLines && Object.keys(drawnLines).length > 0 && (
              <>
                {Object.entries(drawnLines).map(([n, v]) => (
                  <Tag
                    key={n}
                    color="orange"
                    closable
                    onClose={(e) => {
                      e.preventDefault();
                      const next = { ...(drawnLines || {}) };
                      delete next[n];
                      onDrawnLinesChange(next);
                    }}
                  >
                    ✏ {n} = {v.toFixed(2)}
                  </Tag>
                ))}
                <Popconfirm
                  title="清空所有手绘线？"
                  onConfirm={() => onDrawnLinesChange({})}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button size="small" danger icon={<ClearOutlined />}>
                    清空
                  </Button>
                </Popconfirm>
              </>
            )}
          </>
        )}
        <Text type="secondary" style={{ fontSize: 11 }}>
          {drawMode ? '画线模式：点击 K 线任意位置确定价位' : '点击 ▲▼ 查看交易原因'}
        </Text>
      </Space>
      <Spin spinning={loading}>
        <div style={{ position: 'relative', minHeight: height }}>
          <div ref={containerRef} style={{ width: '100%', height }} />
          {!loading && items.length === 0 && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Empty description="无K线数据" />
            </div>
          )}
        </div>
      </Spin>
    </div>
  );
};

export default StrategyLabKlineView;
