import React, { useMemo } from 'react';
import { Card, Empty, Statistic, Row, Col, Tag, Tabs, Table, Alert, Typography } from 'antd';
import {
  AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, Legend, Line,
} from 'recharts';
import type { StrategyLabRunResult, StrategyLabTradeRecord } from '../types';

const { Paragraph, Text } = Typography;

interface Props {
  result: StrategyLabRunResult | null;
  loading: boolean;
}

const fmtPct = (v: number | null | undefined, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(digits)}%`;
};

const fmt = (v: number | null | undefined, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toFixed(digits);
};

export const StrategyLabResultPanel: React.FC<Props> = ({ result, loading }) => {
  const equityChartData = useMemo(() => {
    if (!result?.equity?.length) return [];
    const base = result.equity[0]?.value ?? 1;
    const benchBase = result.equity[0]?.benchmark ?? null;
    return result.equity.map((p) => ({
      date: p.date,
      strategy: base ? (p.value / base) : 0,
      benchmark: benchBase && p.benchmark ? p.benchmark / benchBase : null,
    }));
  }, [result]);

  if (loading && !result) {
    return (
      <Card loading className="strategy-lab-result-empty">
        <div style={{ height: 320 }} />
      </Card>
    );
  }

  if (!result) {
    return (
      <Card className="strategy-lab-result-empty">
        <Empty description={<>点击右上角 <Text code>运行</Text> 开始一次回测</>} />
      </Card>
    );
  }

  if (result.status === 'failed') {
    return (
      <Card>
        <Alert
          type="error"
          showIcon
          message={`回测失败 (run_id=${result.run_id})`}
          description={
            <>
              <Paragraph copyable={{ text: result.error || '' }}>
                {result.error || 'Unknown error'}
              </Paragraph>
              {result.error_traceback && (
                <pre style={{ fontSize: 11, maxHeight: 240, overflow: 'auto', background: '#222', color: '#eee', padding: 8 }}>
                  {result.error_traceback}
                </pre>
              )}
            </>
          }
        />
      </Card>
    );
  }

  const m = result.metrics;
  return (
    <Card
      title={
        <span>
          回测结果
          <Tag color="green" style={{ marginLeft: 8 }}>{result.status}</Tag>
          <Tag color="blue">{result.elapsed_sec.toFixed(2)}s</Tag>
          {result.data_snapshot_at && (
            <Tag color="purple" style={{ marginLeft: 4 }}>data@{result.data_snapshot_at}</Tag>
          )}
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
            run_id: {result.run_id.slice(0, 8)}…
          </Text>
        </span>
      }
      bodyStyle={{ paddingTop: 12 }}
    >
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Statistic
            title="累计收益"
            value={fmtPct(m.cum_return)}
            valueStyle={{ color: m.cum_return >= 0 ? '#3f8600' : '#cf1322' }}
          />
        </Col>
        <Col span={6}>
          <Statistic title="年化" value={fmtPct(m.annual_return)} />
        </Col>
        <Col span={6}>
          <Statistic title="夏普" value={fmt(m.sharpe, 2)} />
        </Col>
        <Col span={6}>
          <Statistic
            title="最大回撤"
            value={fmtPct(m.max_drawdown)}
            valueStyle={{ color: '#cf1322' }}
          />
        </Col>
      </Row>
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={6}><Statistic title="胜率" value={fmtPct(m.win_rate)} /></Col>
        <Col span={6}><Statistic title="交易笔数" value={m.n_trades} /></Col>
        <Col span={6}><Statistic title="平均仓位" value={fmtPct(m.avg_position, 1)} /></Col>
        <Col span={6}><Statistic title="数据点" value={result.equity.length} /></Col>
      </Row>

      <Tabs
        items={[
          {
            key: 'equity',
            label: `净值曲线 (${result.equity.length})`,
            children: equityChartData.length === 0 ? (
              <Empty description="无净值数据" />
            ) : (
              <div style={{ width: '100%', height: 260 }}>
                <ResponsiveContainer>
                  <AreaChart data={equityChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={20} />
                    <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} tickFormatter={(v: number) => v.toFixed(2)} />
                    <Tooltip formatter={(v: number) => v.toFixed(4)} />
                    <Legend />
                    <Area type="monotone" dataKey="strategy" name="策略" stroke="#1677ff" fill="#1677ff22" />
                    {equityChartData.some((d) => d.benchmark !== null) && (
                      <Line type="monotone" dataKey="benchmark" name="基准" stroke="#888" dot={false} />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ),
          },
          {
            key: 'trades',
            label: `成交 (${result.trades.length})`,
            children: <TradeTable trades={result.trades} />,
          },
          {
            key: 'positions',
            label: `末日持仓 (${result.positions.length})`,
            children: result.positions.length === 0 ? (
              <Empty description="末日空仓" />
            ) : (
              <Table
                size="small"
                rowKey={(r) => r.symbol}
                pagination={false}
                dataSource={result.positions}
                columns={[
                  { title: '代码', dataIndex: 'symbol' },
                  { title: '数量', dataIndex: 'qty' },
                  { title: '成本', dataIndex: 'cost', render: (v: number) => fmt(v, 0) },
                  { title: '市值', dataIndex: 'market_value', render: (v: number) => fmt(v, 0) },
                  { title: '盈亏%', dataIndex: 'pnl_pct', render: (v: number) => fmtPct(v) },
                ]}
              />
            ),
          },
          {
            key: 'logs',
            label: `日志 (${result.logs.length})`,
            children: result.logs.length === 0 ? (
              <Empty description="无日志" />
            ) : (
              <pre
                style={{
                  fontSize: 11,
                  background: '#1e1e1e',
                  color: '#d4d4d4',
                  padding: 12,
                  borderRadius: 4,
                  maxHeight: 240,
                  overflow: 'auto',
                  margin: 0,
                }}
              >
                {result.logs
                  .map((l) => `[${l.level.toUpperCase()}] ${l.ts || ''} ${l.msg}`)
                  .join('\n')}
              </pre>
            ),
          },
        ]}
      />
    </Card>
  );
};

const TradeTable: React.FC<{ trades: StrategyLabTradeRecord[] }> = ({ trades }) => {
  if (!trades.length) return <Empty description="无成交" />;
  return (
    <Table
      size="small"
      rowKey={(_, i) => String(i)}
      pagination={{ pageSize: 50, showSizeChanger: false }}
      scroll={{ y: 280 }}
      dataSource={trades}
      columns={[
        { title: '日期', dataIndex: 'date', width: 100 },
        { title: '代码', dataIndex: 'symbol', width: 100 },
        {
          title: '方向',
          dataIndex: 'direction',
          width: 70,
          render: (v: string) => (
            <Tag color={v === 'BUY' ? 'red' : 'green'}>{v}</Tag>
          ),
        },
        { title: '价格', dataIndex: 'price', width: 80, render: (v: number) => fmt(v, 2) },
        { title: '数量', dataIndex: 'qty', width: 80 },
        {
          title: 'PnL',
          dataIndex: 'pnl',
          width: 80,
          render: (v: number | null) =>
            v === null || v === undefined ? '—' : (
              <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>{fmt(v, 0)}</span>
            ),
        },
        { title: '原因', dataIndex: 'reason', ellipsis: true },
      ]}
    />
  );
};

export default StrategyLabResultPanel;
