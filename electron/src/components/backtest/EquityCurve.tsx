/**
 * 权益曲线组件
 * 展示回测的权益变化和回撤
 */

import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, Time } from 'lightweight-charts';
import { EquityCurve } from '../../types/backtest';

interface EquityCurveProps {
  equityCurve: EquityCurve;
  initialCapital: number;
  benchmarkData?: { timestamp: number; value: number }[];
}

export const EquityCurveChart: React.FC<EquityCurveProps> = ({
  equityCurve,
  initialCapital,
  benchmarkData
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const equitySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const benchmarkSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 创建图表
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 400,
      layout: {
        background: { color: '#1e1e1e' },
        textColor: '#d4d4d4',
      },
      grid: {
        vertLines: { color: '#2e2e2e' },
        horzLines: { color: '#2e2e2e' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#4a4a4a',
      },
      timeScale: {
        borderColor: '#4a4a4a',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // 添加权益曲线
    const equitySeries = (chart as any).addLineSeries({
      color: '#2962ff',
      lineWidth: 2,
      title: '策略权益',
    });
    equitySeriesRef.current = equitySeries;

    // 添加基准曲线（如果有）
    if (benchmarkData) {
      const benchmarkSeries = (chart as any).addLineSeries({
        color: '#f44336',
        lineWidth: 2,
        title: '基准收益',
        lineStyle: 2, // 虚线
      });
      benchmarkSeriesRef.current = benchmarkSeries;
    }

    // 处理窗口大小变化
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [benchmarkData]);

  useEffect(() => {
    if (!equitySeriesRef.current) return;

    // 更新权益曲线数据
    const equityData = equityCurve.timestamps.map((ts, i) => ({
      time: (ts / 1000) as Time,
      value: equityCurve.values[i],
    }));

    equitySeriesRef.current.setData(equityData);

    // 更新基准数据
    if (benchmarkSeriesRef.current && benchmarkData) {
      const benchmark = benchmarkData.map(d => ({
        time: (d.timestamp / 1000) as Time,
        value: d.value,
      }));
      benchmarkSeriesRef.current.setData(benchmark);
    }

    // 自动缩放
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [equityCurve, benchmarkData]);

  // 计算统计数据
  const finalEquity = equityCurve.values[equityCurve.values.length - 1];
  const totalReturn = ((finalEquity - initialCapital) / initialCapital) * 100;
  const maxEquity = Math.max(...equityCurve.values);
  const minEquity = Math.min(...equityCurve.values);
  const maxDrawdown = Math.max(...equityCurve.drawdowns) * 100;

  return (
    <div className="equity-curve-chart">
      <div className="chart-header">
        <h3>权益曲线</h3>
        <div className="chart-stats">
          <div className="stat">
            <span className="stat-label">初始资金:</span>
            <span className="stat-value">${initialCapital.toLocaleString()}</span>
          </div>
          <div className="stat">
            <span className="stat-label">最终权益:</span>
            <span className="stat-value">${finalEquity.toLocaleString()}</span>
          </div>
          <div className="stat">
            <span className="stat-label">总收益率:</span>
            <span className={`stat-value ${totalReturn >= 0 ? 'positive' : 'negative'}`}>
              {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
            </span>
          </div>
          <div className="stat">
            <span className="stat-label">最大回撤:</span>
            <span className="stat-value negative">
              -{maxDrawdown.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>

      <div ref={chartContainerRef} className="chart-container" />

      <div className="equity-range">
        <div className="range-item">
          <span className="range-label">最高权益:</span>
          <span className="range-value">${maxEquity.toLocaleString()}</span>
        </div>
        <div className="range-item">
          <span className="range-label">最低权益:</span>
          <span className="range-value">${minEquity.toLocaleString()}</span>
        </div>
      </div>

      <style>{`
        .equity-curve-chart {
          background: #252526;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .chart-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .chart-header h3 {
          margin: 0;
          color: #d4d4d4;
          font-size: 18px;
        }

        .chart-stats {
          display: flex;
          gap: 24px;
        }

        .stat {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .stat-label {
          font-size: 12px;
          color: #969696;
        }

        .stat-value {
          font-size: 16px;
          font-weight: 600;
          color: #d4d4d4;
        }

        .stat-value.positive {
          color: #26a269;
        }

        .stat-value.negative {
          color: #f66151;
        }

        .chart-container {
          margin: 16px 0;
          border-radius: 4px;
          overflow: hidden;
        }

        .equity-range {
          display: flex;
          gap: 32px;
          padding-top: 12px;
          border-top: 1px solid #3e3e42;
        }

        .range-item {
          display: flex;
          gap: 12px;
          align-items: center;
        }

        .range-label {
          font-size: 13px;
          color: #969696;
        }

        .range-value {
          font-size: 14px;
          font-weight: 500;
          color: #d4d4d4;
        }
      `}</style>
    </div>
  );
};
