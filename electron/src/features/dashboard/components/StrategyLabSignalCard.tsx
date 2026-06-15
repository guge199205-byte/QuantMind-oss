/**
 * Dashboard signal card — renders the latest output of the Strategy Lab
 * daily scan (qm:lab:signals:latest). Wired into DashboardPage as a
 * compact list under "策略实验室扫描".
 *
 * Day 16 of the Strategy Lab spec.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, Empty, Tag, Tooltip, Typography, Button, Space, Spin, message } from 'antd';
import { ReloadOutlined, ExperimentOutlined } from '@ant-design/icons';
import { strategyLabService } from '../../strategy-lab/services/strategyLabService';

const { Text } = Typography;

interface Signal {
  strategy: string;
  script_sha: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  price?: number;
  qty?: number;
  reason?: string;
  date: string;
}

const StrategyLabSignalCard: React.FC = () => {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await strategyLabService.fetchSignals();
      setSignals(resp.signals || []);
      setGeneratedAt(resp.generated_at);
    } catch {
      // best-effort widget — silent failure
    } finally {
      setLoading(false);
    }
  }, []);

  const runNow = useCallback(async () => {
    setScanning(true);
    try {
      const resp = await strategyLabService.runScanNow(7);
      setSignals(resp.signals || []);
      setGeneratedAt(resp.generated_at);
      message.success(`扫描完成：${(resp.signals || []).length} 条新信号`);
    } catch (e: any) {
      message.error(`扫描失败: ${e?.response?.data?.detail || e?.message || e}`);
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const ts = generatedAt ? new Date(generatedAt).toLocaleString() : '尚未运行';

  return (
    <Card
      size="small"
      title={
        <Space size="small">
          <ExperimentOutlined />
          <span>策略实验室扫描</span>
          <Text type="secondary" style={{ fontSize: 11 }}>{ts}</Text>
        </Space>
      }
      extra={
        <Space size="small">
          <Tooltip title="立即扫描全部 watch 列表">
            <Button size="small" icon={<ReloadOutlined />} loading={scanning} onClick={runNow}>
              立即扫描
            </Button>
          </Tooltip>
        </Space>
      }
      bodyStyle={{ padding: 8, maxHeight: 360, overflow: 'auto' }}
    >
      <Spin spinning={loading}>
        {signals.length === 0 ? (
          <Empty description="今天的 watch 列表暂未触发信号" />
        ) : (
          <ul style={{ margin: 0, paddingLeft: 12, fontSize: 12 }}>
            {signals.map((s, i) => (
              <li key={i} style={{ marginBottom: 6 }}>
                <Tag color="purple">{s.strategy}</Tag>
                <Tag color={s.direction === 'BUY' ? 'red' : 'green'}>{s.direction}</Tag>
                <Text strong>{s.symbol}</Text>
                {s.price !== undefined && (
                  <Text type="secondary"> @ {Number(s.price).toFixed(2)}</Text>
                )}
                {s.reason && (
                  <span style={{ color: '#475569', marginLeft: 6 }}>{s.reason}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Spin>
    </Card>
  );
};

export default StrategyLabSignalCard;
