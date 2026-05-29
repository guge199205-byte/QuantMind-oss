/**
 * 多周期图表组件
 * 支持同时显示多个时间周期的K线图
 */

import React, { useEffect, useRef, useState } from 'react';
import { Period, OHLCV } from '../../../services/chart/MultiPeriodDataService';

export interface MultiPeriodChartProps {
  data: Map<string, OHLCV[]>;
  periods: Period[];
  width?: number;
  height?: number;
  showVolume?: boolean;
  showGrid?: boolean;
  syncCrosshair?: boolean;
  className?: string;
}

/**
 * 多周期图表组件
 */
export const MultiPeriodChart: React.FC<MultiPeriodChartProps> = ({
  data,
  periods,
  width = 800,
  height = 400,
  showVolume = true,
  showGrid = true,
  syncCrosshair = true,
  className = ''
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [crosshairPosition, setCrosshairPosition] = useState<{ x: number; y: number } | null>(null);
  const [hoveredPeriod, setHoveredPeriod] = useState<string | null>(null);

  // 绘制图表
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 绘制背景
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);

    // 绘制网格
    if (showGrid) {
      drawGrid(ctx, width, height);
    }

    // 绘制每个周期的K线
    const enabledPeriods = periods.filter(p => p.enabled);
    enabledPeriods.forEach((period, index) => {
      const periodData = data.get(period.id);
      if (periodData && periodData.length > 0) {
        drawCandlesticks(ctx, periodData, period, width, height, index, enabledPeriods.length);
      }
    });

    // 绘制十字线
    if (syncCrosshair && crosshairPosition) {
      drawCrosshair(ctx, crosshairPosition.x, crosshairPosition.y, width, height);
    }
  }, [data, periods, width, height, showVolume, showGrid, syncCrosshair, crosshairPosition]);

  // 绘制网格
  const drawGrid = (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;

    // 垂直网格线
    for (let i = 0; i <= 10; i++) {
      const x = (w / 10) * i;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }

    // 水平网格线
    for (let i = 0; i <= 8; i++) {
      const y = (h / 8) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
  };

  // 绘制K线
  const drawCandlesticks = (
    ctx: CanvasRenderingContext2D,
    periodData: OHLCV[],
    period: Period,
    w: number,
    h: number,
    periodIndex: number,
    totalPeriods: number
  ) => {
    if (periodData.length === 0) return;

    // 计算价格范围
    const prices = periodData.flatMap(d => [d.high, d.low]);
    const maxPrice = Math.max(...prices);
    const minPrice = Math.min(...prices);
    const priceRange = maxPrice - minPrice;

    // 计算每根K线的宽度
    const candleWidth = Math.max(2, w / periodData.length - 2);
    const candleSpacing = w / periodData.length;

    // 绘制K线
    periodData.forEach((candle, index) => {
      const x = index * candleSpacing + candleSpacing / 2;
      const openY = h - ((candle.open - minPrice) / priceRange) * h;
      const closeY = h - ((candle.close - minPrice) / priceRange) * h;
      const highY = h - ((candle.high - minPrice) / priceRange) * h;
      const lowY = h - ((candle.low - minPrice) / priceRange) * h;

      const isUp = candle.close >= candle.open;
      const color = period.color;
      const alpha = hoveredPeriod === period.id ? 1.0 : 0.6;

      // 绘制影线
      ctx.strokeStyle = color;
      ctx.globalAlpha = alpha;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, highY);
      ctx.lineTo(x, lowY);
      ctx.stroke();

      // 绘制实体
      if (isUp) {
        ctx.fillStyle = color;
        ctx.globalAlpha = alpha * 0.3;
      } else {
        ctx.fillStyle = color;
        ctx.globalAlpha = alpha;
      }

      const bodyHeight = Math.abs(closeY - openY);
      const bodyY = Math.min(openY, closeY);
      ctx.fillRect(x - candleWidth / 2, bodyY, candleWidth, Math.max(1, bodyHeight));

      ctx.globalAlpha = 1.0;
    });
  };

  // 绘制十字线
  const drawCrosshair = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number
  ) => {
    ctx.strokeStyle = '#6b7280';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);

    // 垂直线
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();

    // 水平线
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();

    ctx.setLineDash([]);
  };

  // 处理鼠标移动
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!syncCrosshair) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setCrosshairPosition({ x, y });
  };

  // 处理鼠标离开
  const handleMouseLeave = () => {
    if (syncCrosshair) {
      setCrosshairPosition(null);
    }
  };

  return (
    <div className={`multi-period-chart ${className}`}>
      <div className="multi-period-chart__header">
        <h3 className="multi-period-chart__title">多周期对比</h3>
        <div className="multi-period-chart__legend">
          {periods.filter(p => p.enabled).map(period => (
            <div
              key={period.id}
              className={`legend-item ${hoveredPeriod === period.id ? 'legend-item--active' : ''}`}
              onMouseEnter={() => setHoveredPeriod(period.id)}
              onMouseLeave={() => setHoveredPeriod(null)}
            >
              <span
                className="legend-item__color"
                style={{ backgroundColor: period.color }}
              ></span>
              <span className="legend-item__name">{period.name}</span>
            </div>
          ))}
        </div>
      </div>

      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="multi-period-chart__canvas"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />

      <style>{`
        .multi-period-chart {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 16px;
          background: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .multi-period-chart__header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-bottom: 12px;
          border-bottom: 1px solid #e5e7eb;
        }

        .multi-period-chart__title {
          font-size: 16px;
          font-weight: 600;
          color: #111827;
          margin: 0;
        }

        .multi-period-chart__legend {
          display: flex;
          gap: 16px;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
          cursor: pointer;
          transition: opacity 0.2s ease;
        }

        .legend-item:hover {
          opacity: 1;
        }

        .legend-item--active {
          opacity: 1;
        }

        .legend-item__color {
          width: 12px;
          height: 12px;
          border-radius: 2px;
        }

        .legend-item__name {
          font-size: 13px;
          color: #6b7280;
        }

        .multi-period-chart__canvas {
          border: 1px solid #e5e7eb;
          border-radius: 4px;
          cursor: crosshair;
        }

      `}</style>
    </div>
  );
};

/**
 * 周期对比卡片组件
 */
export interface PeriodComparisonCardProps {
  period: Period;
  data: OHLCV[];
  baseData: OHLCV[];
  isActive?: boolean;
  onClick?: () => void;
  className?: string;
}

export const PeriodComparisonCard: React.FC<PeriodComparisonCardProps> = ({
  period,
  data,
  baseData,
  isActive = false,
  onClick,
  className = ''
}) => {
  // 计算统计数据
  const stats = React.useMemo(() => {
    if (data.length === 0) return null;

    const latestPrice = data[data.length - 1].close;
    const firstPrice = data[0].close;
    const change = latestPrice - firstPrice;
    const changePercent = (change / firstPrice) * 100;

    const maxPrice = Math.max(...data.map(d => d.high));
    const minPrice = Math.min(...data.map(d => d.low));
    const avgVolume = data.reduce((sum, d) => sum + d.volume, 0) / data.length;

    return {
      latestPrice,
      change,
      changePercent,
      maxPrice,
      minPrice,
      avgVolume
    };
  }, [data]);

  if (!stats) return null;

  return (
    <div
      className={`period-comparison-card ${isActive ? 'period-comparison-card--active' : ''} ${className}`}
      onClick={onClick}
      style={{ borderLeftColor: period.color }}
    >
      <div className="period-comparison-card__header">
        <span className="period-comparison-card__name">{period.name}</span>
        <span
          className={`period-comparison-card__change ${
            stats.change >= 0 ? 'period-comparison-card__change--up' : 'period-comparison-card__change--down'
          }`}
        >
          {stats.changePercent >= 0 ? '+' : ''}
          {stats.changePercent.toFixed(2)}%
        </span>
      </div>

      <div className="period-comparison-card__stats">
        <div className="stat-item">
          <span className="stat-item__label">最新价</span>
          <span className="stat-item__value">{stats.latestPrice.toFixed(2)}</span>
        </div>
        <div className="stat-item">
          <span className="stat-item__label">最高</span>
          <span className="stat-item__value">{stats.maxPrice.toFixed(2)}</span>
        </div>
        <div className="stat-item">
          <span className="stat-item__label">最低</span>
          <span className="stat-item__value">{stats.minPrice.toFixed(2)}</span>
        </div>
      </div>

      <style>{`
        .period-comparison-card {
          padding: 12px;
          border-left: 3px solid;
          background: #ffffff;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .period-comparison-card:hover {
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          transform: translateY(-2px);
        }

        .period-comparison-card--active {
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          transform: translateY(-4px);
        }

        .period-comparison-card__header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .period-comparison-card__name {
          font-size: 14px;
          font-weight: 600;
          color: #111827;
        }

        .period-comparison-card__change {
          font-size: 13px;
          font-weight: 600;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .period-comparison-card__change--up {
          color: #10b981;
          background: #d1fae5;
        }

        .period-comparison-card__change--down {
          color: #ef4444;
          background: #fee2e2;
        }

        .period-comparison-card__stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
        }

        .stat-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .stat-item__label {
          font-size: 11px;
          color: #6b7280;
        }

        .stat-item__value {
          font-size: 13px;
          font-weight: 500;
          color: #111827;
        }

      `}</style>
    </div>
  );
};

export default MultiPeriodChart;
