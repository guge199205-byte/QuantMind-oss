import React, { useMemo } from 'react';
import { Card, Empty, Tag, Tabs, Table, Alert, Typography } from 'antd';
import type { StrategyLabRunResult, StrategyLabTradeRecord } from '../types';
import KpiCards from './KpiCards';
import EquityChart from './EquityChart';
import MonthlyReturnsHeatmap from './MonthlyReturnsHeatmap';

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
  const alpha = useMemo(() => {
    if (!result?.equity?.length) return null;
    const last = result.equity[result.equity.length - 1];
    const first = result.equity[0];
    if (!first || !last) return null;
    const stratRet = first.value ? last.value / first.value - 1 : 0;
    if (first.benchmark === null || first.benchmark === undefined || last.benchmark === null || last.benchmark === undefined) {
      return null;
    }
    const benchRet = first.benchmark ? last.benchmark / first.benchmark - 1 : 0;
    return stratRet - benchRet;
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
      <KpiCards
        metrics={result.metrics}
        extras={{
          alpha,
          nDataPoints: result.equity.length,
        }}
      />

      <Tabs
        defaultActiveKey="equity"
        style={{ marginTop: 12 }}
        items={[
          {
            key: 'equity',
            label: `净值曲线 (${result.equity.length})`,
            children: <EquityChart equity={result.equity} height={300} />,
          },
          {
            key: 'monthly',
            label: '月度热力',
            children: <MonthlyReturnsHeatmap equity={result.equity} />,
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
          ...(result.warnings.length > 0
            ? [
                {
                  key: 'warnings',
                  label: `提示 (${result.warnings.length})`,
                  children: (
                    <Alert
                      type="warning"
                      showIcon
                      message="回测引擎产生以下提示"
                      description={
                        <ul style={{ margin: 0, paddingLeft: 20 }}>
                          {result.warnings.map((w, i) => (
                            <li key={i} style={{ fontSize: 12 }}>{w}</li>
                          ))}
                        </ul>
                      }
                    />
                  ),
                },
              ]
            : []),
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
