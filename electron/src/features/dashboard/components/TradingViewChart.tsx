import React, { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, HistogramSeries, type IChartApi } from 'lightweight-charts';
import type { KlineItem } from '../services/dataDashboardService';

interface TradingViewChartProps {
  data: KlineItem[];
  height?: number;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({ data, height = 550 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Cleanup previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: 0, // Normal
      },
      rightPriceScale: {
        borderColor: '#e5e7eb',
      },
      timeScale: {
        borderColor: '#e5e7eb',
        timeVisible: false,
      },
    });

    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#10b981',
      borderUpColor: '#ef4444',
      borderDownColor: '#10b981',
      wickUpColor: '#ef4444',
      wickDownColor: '#10b981',
    });

    // Volume series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    if (data && data.length > 0) {
      const candleData = data.map((d) => ({
        time: d.date as string,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));

      const volumeData = data.map((d) => ({
        time: d.date as string,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(239,68,68,0.4)' : 'rgba(16,185,129,0.4)',
      }));

      candleSeries.setData(candleData);
      volumeSeries.setData(volumeData);
      chart.timeScale().fitContent();
    }

    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [data, height]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: `${height}px`,
        borderRadius: 8,
        overflow: 'hidden',
      }}
    />
  );
};
