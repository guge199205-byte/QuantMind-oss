/**
 * 绩效指标展示组件
 * 展示回测的各项绩效指标
 */

import React from 'react';
import { PerformanceMetrics } from '../../types/backtest';

interface PerformanceMetricsProps {
  metrics: PerformanceMetrics;
}

export const PerformanceMetricsPanel: React.FC<PerformanceMetricsProps> = ({ metrics }) => {
  // 指标卡片数据
  const mainMetrics = [
    {
      label: '总收益率',
      value: `${(metrics.totalReturn * 100).toFixed(2)}%`,
      positive: metrics.totalReturn >= 0,
      icon: '📈'
    },
    {
      label: '年化收益率',
      value: `${(metrics.annualizedReturn * 100).toFixed(2)}%`,
      positive: metrics.annualizedReturn >= 0,
      icon: '📊'
    },
    {
      label: '夏普比率',
      value: metrics.sharpeRatio.toFixed(2),
      positive: metrics.sharpeRatio >= 1,
      icon: '⚖️'
    },
    {
      label: '最大回撤',
      value: `${(metrics.maxDrawdown * 100).toFixed(2)}%`,
      positive: false,
      icon: '📉'
    }
  ];

  const tradeMetrics = [
    {
      label: '总交易次数',
      value: metrics.totalTrades.toString(),
      icon: '🔢'
    },
    {
      label: '盈利次数',
      value: metrics.winningTrades.toString(),
      positive: true,
      icon: '✅'
    },
    {
      label: '亏损次数',
      value: metrics.losingTrades.toString(),
      positive: false,
      icon: '❌'
    },
    {
      label: '胜率',
      value: `${(metrics.winRate * 100).toFixed(2)}%`,
      positive: metrics.winRate >= 0.5,
      icon: '🎯'
    }
  ];

  const profitMetrics = [
    {
      label: '平均盈利',
      value: `$${metrics.averageWin.toFixed(2)}`,
      positive: true,
      icon: '💰'
    },
    {
      label: '平均亏损',
      value: `$${Math.abs(metrics.averageLoss).toFixed(2)}`,
      positive: false,
      icon: '💸'
    },
    {
      label: '盈亏比',
      value: metrics.profitFactor.toFixed(2),
      positive: metrics.profitFactor >= 1,
      icon: '⚡'
    },
    {
      label: '最大回撤持续期',
      value: `${metrics.maxDrawdownDuration}天`,
      positive: false,
      icon: '⏱️'
    }
  ];

  // 评级函数
  const getRating = () => {
    let score = 0;

    if (metrics.totalReturn > 0.2) score += 1;
    if (metrics.sharpeRatio > 1.5) score += 1;
    if (metrics.maxDrawdown < 0.2) score += 1;
    if (metrics.winRate > 0.5) score += 1;
    if (metrics.profitFactor > 1.5) score += 1;

    if (score >= 4) return { text: '优秀', color: '#26a269', emoji: '🌟' };
    if (score >= 3) return { text: '良好', color: '#0e639c', emoji: '👍' };
    if (score >= 2) return { text: '中等', color: '#e5a50a', emoji: '⚠️' };
    return { text: '较差', color: '#f66151', emoji: '⚠️' };
  };

  const rating = getRating();

  return (
    <div className="performance-metrics">
      <div className="metrics-header">
        <h3>绩效指标</h3>
        <div className="rating-badge" style={{ backgroundColor: rating.color }}>
          {rating.emoji} {rating.text}
        </div>
      </div>

      {/* 主要指标 */}
      <div className="metrics-section">
        <h4>收益与风险</h4>
        <div className="metrics-grid">
          {mainMetrics.map((metric, index) => (
            <div key={index} className="metric-card">
              <div className="metric-icon">{metric.icon}</div>
              <div className="metric-content">
                <div className="metric-label">{metric.label}</div>
                <div className={`metric-value ${metric.positive ? 'positive' : metric.positive === false ? 'negative' : ''}`}>
                  {metric.value}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 交易指标 */}
      <div className="metrics-section">
        <h4>交易统计</h4>
        <div className="metrics-grid">
          {tradeMetrics.map((metric, index) => (
            <div key={index} className="metric-card">
              <div className="metric-icon">{metric.icon}</div>
              <div className="metric-content">
                <div className="metric-label">{metric.label}</div>
                <div className={`metric-value ${metric.positive ? 'positive' : metric.positive === false ? 'negative' : ''}`}>
                  {metric.value}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 盈亏指标 */}
      <div className="metrics-section">
        <h4>盈亏分析</h4>
        <div className="metrics-grid">
          {profitMetrics.map((metric, index) => (
            <div key={index} className="metric-card">
              <div className="metric-icon">{metric.icon}</div>
              <div className="metric-content">
                <div className="metric-label">{metric.label}</div>
                <div className={`metric-value ${metric.positive ? 'positive' : metric.positive === false ? 'negative' : ''}`}>
                  {metric.value}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 周期收益 */}
      <div className="metrics-section">
        <h4>周期收益</h4>
        <div className="period-returns">
          <div className="period-card">
            <div className="period-label">日收益</div>
            <div className="period-stats">
              <div className="period-stat">
                <span className="period-stat-label">平均:</span>
                <span className="period-stat-value">
                  {(metrics.dailyReturns.reduce((a, b) => a + b, 0) / metrics.dailyReturns.length * 100).toFixed(2)}%
                </span>
              </div>
              <div className="period-stat">
                <span className="period-stat-label">最大:</span>
                <span className="period-stat-value positive">
                  {(Math.max(...metrics.dailyReturns) * 100).toFixed(2)}%
                </span>
              </div>
              <div className="period-stat">
                <span className="period-stat-label">最小:</span>
                <span className="period-stat-value negative">
                  {(Math.min(...metrics.dailyReturns) * 100).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>

          <div className="period-card">
            <div className="period-label">周收益</div>
            <div className="period-stats">
              <div className="period-stat">
                <span className="period-stat-label">平均:</span>
                <span className="period-stat-value">
                  {(metrics.weeklyReturns.reduce((a, b) => a + b, 0) / metrics.weeklyReturns.length * 100).toFixed(2)}%
                </span>
              </div>
              <div className="period-stat">
                <span className="period-stat-label">最大:</span>
                <span className="period-stat-value positive">
                  {(Math.max(...metrics.weeklyReturns) * 100).toFixed(2)}%
                </span>
              </div>
              <div className="period-stat">
                <span className="period-stat-label">最小:</span>
                <span className="period-stat-value negative">
                  {(Math.min(...metrics.weeklyReturns) * 100).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>

          <div className="period-card">
            <div className="period-label">月收益</div>
            <div className="period-stats">
              <div className="period-stat">
                <span className="period-stat-label">平均:</span>
                <span className="period-stat-value">
                  {(metrics.monthlyReturns.reduce((a, b) => a + b, 0) / metrics.monthlyReturns.length * 100).toFixed(2)}%
                </span>
              </div>
              <div className="period-stat">
                <span className="period-stat-label">最大:</span>
                <span className="period-stat-value positive">
                  {(Math.max(...metrics.monthlyReturns) * 100).toFixed(2)}%
                </span>
              </div>
              <div className="period-stat">
                <span className="period-stat-label">最小:</span>
                <span className="period-stat-value negative">
                  {(Math.min(...metrics.monthlyReturns) * 100).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .performance-metrics {
          background: #252526;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .metrics-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .metrics-header h3 {
          margin: 0;
          color: #d4d4d4;
          font-size: 18px;
        }

        .rating-badge {
          padding: 6px 16px;
          border-radius: 16px;
          color: white;
          font-weight: 600;
          font-size: 14px;
        }

        .metrics-section {
          margin-bottom: 24px;
        }

        .metrics-section h4 {
          margin: 0 0 12px 0;
          color: #969696;
          font-size: 14px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 12px;
        }

        .metric-card {
          background: #1e1e1e;
          padding: 16px;
          border-radius: 8px;
          display: flex;
          gap: 12px;
          align-items: center;
          transition: transform 0.2s;
        }

        .metric-card:hover {
          transform: translateY(-2px);
        }

        .metric-icon {
          font-size: 28px;
        }

        .metric-content {
          flex: 1;
        }

        .metric-label {
          font-size: 12px;
          color: #969696;
          margin-bottom: 4px;
        }

        .metric-value {
          font-size: 20px;
          font-weight: 700;
          color: #d4d4d4;
        }

        .metric-value.positive {
          color: #26a269;
        }

        .metric-value.negative {
          color: #f66151;
        }

        .period-returns {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
        }

        .period-card {
          background: #1e1e1e;
          padding: 16px;
          border-radius: 8px;
        }

        .period-label {
          font-size: 14px;
          font-weight: 600;
          color: #d4d4d4;
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid #3e3e42;
        }

        .period-stats {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .period-stat {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .period-stat-label {
          font-size: 12px;
          color: #969696;
        }

        .period-stat-value {
          font-size: 14px;
          font-weight: 600;
          color: #d4d4d4;
        }

        .period-stat-value.positive {
          color: #26a269;
        }

        .period-stat-value.negative {
          color: #f66151;
        }

        @media (max-width: 1200px) {
          .metrics-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 768px) {
          .metrics-grid,
          .period-returns {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};
