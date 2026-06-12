/**
 * Reusable KPI grid for Strategy Lab + future overfitting reports.
 *
 * Pure presentational — caller passes the metrics dict + optional extras
 * (final_equity, alpha, n_days). The grid is responsive (Row gutter).
 */

import React from 'react';
import { Row, Col, Statistic, Tooltip } from 'antd';
import type { StrategyLabMetrics } from '../types';

const fmtPct = (v: number | null | undefined, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(digits)}%`;
};
const fmt = (v: number | null | undefined, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toFixed(digits);
};

interface Props {
  metrics: StrategyLabMetrics;
  extras?: {
    finalEquity?: number;
    initialCapital?: number;
    alpha?: number | null;
    nDays?: number;
    nDataPoints?: number;
  };
}

export const KpiCards: React.FC<Props> = ({ metrics: m, extras }) => {
  const cumReturn = m.cum_return ?? 0;
  const cumColor = cumReturn >= 0 ? '#3f8600' : '#cf1322';
  return (
    <>
      <Row gutter={[12, 12]} style={{ marginBottom: 8 }}>
        <Col xs={12} sm={8} md={6}>
          <Tooltip title="期末权益 / 初始权益 - 1">
            <Statistic
              title="累计收益"
              value={fmtPct(m.cum_return)}
              valueStyle={{ color: cumColor, fontSize: 18 }}
            />
          </Tooltip>
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Tooltip title="(1+累计收益)^(252/N天) - 1">
            <Statistic title="年化收益" value={fmtPct(m.annual_return)} valueStyle={{ fontSize: 18 }} />
          </Tooltip>
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Tooltip title="日收益均值 / 标准差 × √252">
            <Statistic title="夏普比率" value={fmt(m.sharpe, 2)} valueStyle={{ fontSize: 18 }} />
          </Tooltip>
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Tooltip title="历史峰值到谷底的最大跌幅">
            <Statistic
              title="最大回撤"
              value={fmtPct(m.max_drawdown)}
              valueStyle={{ color: '#cf1322', fontSize: 18 }}
            />
          </Tooltip>
        </Col>
      </Row>
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="胜率" value={fmtPct(m.win_rate)} valueStyle={{ fontSize: 16 }} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="交易笔数" value={m.n_trades} valueStyle={{ fontSize: 16 }} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <Statistic title="平均仓位" value={fmtPct(m.avg_position, 1)} valueStyle={{ fontSize: 16 }} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          {extras?.alpha !== undefined && extras?.alpha !== null ? (
            <Tooltip title="策略累计收益 − 基准累计收益">
              <Statistic
                title="超额 (vs 基准)"
                value={fmtPct(extras.alpha)}
                valueStyle={{
                  fontSize: 16,
                  color: extras.alpha >= 0 ? '#3f8600' : '#cf1322',
                }}
              />
            </Tooltip>
          ) : (
            <Statistic title="数据点" value={extras?.nDataPoints ?? 0} valueStyle={{ fontSize: 16 }} />
          )}
        </Col>
      </Row>
    </>
  );
};

export default KpiCards;
