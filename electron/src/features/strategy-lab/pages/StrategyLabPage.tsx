import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layout, List, Button, Tag, Space, message, Progress, Tooltip, Typography, Card } from 'antd';
import { PlayCircleOutlined, StopOutlined, FileTextOutlined } from '@ant-design/icons';
import Editor, { OnMount } from '@monaco-editor/react';
import { strategyLabService } from '../services/strategyLabService';
import { STRATEGY_LAB_SNIPPETS } from '../components/snippets';
import type {
  StrategyLabPhase,
  StrategyLabRunResult,
} from '../types';
import StrategyLabResultPanel from '../components/StrategyLabResultPanel';

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

const phaseLabel: Record<StrategyLabPhase, string> = {
  queued: '排队中',
  boot: '启动子进程',
  ast_check: '语法检查',
  setup: '加载脚本',
  load_data: '准备数据',
  backtest: '回测中',
  aggregate: '汇总指标',
  done: '完成',
};

const StrategyLabPage: React.FC = () => {
  const [code, setCode] = useState<string>(STRATEGY_LAB_SNIPPETS[0].code);
  const [activeSnippet, setActiveSnippet] = useState<string>(STRATEGY_LAB_SNIPPETS[0].id);
  const [running, setRunning] = useState(false);
  const [pct, setPct] = useState(0);
  const [phase, setPhase] = useState<StrategyLabPhase>('queued');
  const [phaseMsg, setPhaseMsg] = useState('');
  const [result, setResult] = useState<StrategyLabRunResult | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const cancelPollRef = useRef<null | (() => void)>(null);
  const editorRef = useRef<any>(null);

  const handleEditorMount: OnMount = useCallback((editor) => {
    editorRef.current = editor;
  }, []);

  const handleSnippetSelect = useCallback((id: string) => {
    const s = STRATEGY_LAB_SNIPPETS.find((x) => x.id === id);
    if (!s) return;
    setActiveSnippet(id);
    setCode(s.code);
  }, []);

  const stopPolling = useCallback(() => {
    if (cancelPollRef.current) {
      cancelPollRef.current();
      cancelPollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const handleRun = useCallback(async () => {
    if (running) return;
    if (!code.trim()) {
      message.warning('请先粘贴或选择一段策略代码');
      return;
    }
    setRunning(true);
    setResult(null);
    setPct(2);
    setPhase('queued');
    setPhaseMsg('提交中…');

    try {
      const submitResp = await strategyLabService.submit({ code });
      setRunId(submitResp.run_id);
      setPhaseMsg(`run_id=${submitResp.run_id.slice(0, 8)}…`);

      cancelPollRef.current = strategyLabService.pollProgress(
        submitResp.run_id,
        (evt) => {
          setPct(Math.max(2, Math.min(99, Math.round(evt.pct))));
          setPhase(evt.phase);
          if (evt.message) setPhaseMsg(evt.message);
        },
        (final) => {
          setRunning(false);
          setPct(100);
          setPhase('done');
          if (final) {
            setResult(final);
            if (final.status === 'success') {
              message.success(
                `回测完成 · 累计收益 ${(final.metrics.cum_return * 100).toFixed(2)}% · ${final.metrics.n_trades} 笔交易`,
              );
            } else if (final.status === 'failed') {
              message.error(`回测失败: ${final.error?.slice(0, 80) || 'unknown'}`);
            }
          } else {
            message.error('未能获取回测结果，请稍后重试');
          }
          stopPolling();
        },
      );
    } catch (err: any) {
      setRunning(false);
      setPct(0);
      const detail = err?.response?.data?.detail || err?.message || '提交失败';
      message.error(`提交失败: ${detail}`);
    }
  }, [code, running, stopPolling]);

  const handleStop = useCallback(() => {
    stopPolling();
    setRunning(false);
    setPct(0);
    setPhase('queued');
    setPhaseMsg('已取消');
    message.info('已停止状态轮询（后端任务仍可能运行至完成）');
  }, [stopPolling]);

  const sider = useMemo(
    () => (
      <Sider width={260} theme="light" style={{ borderRight: '1px solid #eee', padding: 12 }}>
        <Title level={5} style={{ marginBottom: 8 }}>
          <FileTextOutlined /> 示例策略
        </Title>
        <List
          dataSource={STRATEGY_LAB_SNIPPETS}
          renderItem={(item) => (
            <List.Item
              onClick={() => handleSnippetSelect(item.id)}
              style={{
                cursor: 'pointer',
                padding: '8px 4px',
                background: activeSnippet === item.id ? '#e6f4ff' : 'transparent',
                borderRadius: 6,
              }}
            >
              <List.Item.Meta
                title={<span style={{ fontSize: 13 }}>{item.title}</span>}
                description={<Text type="secondary" style={{ fontSize: 11 }}>{item.description}</Text>}
              />
            </List.Item>
          )}
        />
        <div style={{ marginTop: 16, fontSize: 11, color: '#888' }}>
          <p>更多示例与 AI 助手将在后续 Sprint 上线。</p>
          <p>当前支持 SDK 接口：<code>ctx.universe / ctx.start / ctx.end / ctx.cash</code>，
          策略钩子：<code>setup / on_bar / on_universe / on_finish</code>。</p>
        </div>
      </Sider>
    ),
    [activeSnippet, handleSnippetSelect],
  );

  return (
    <Layout style={{ height: 'calc(100vh - 60px)', background: '#fafafa' }}>
      {sider}
      <Layout>
        <Content style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card
            size="small"
            bodyStyle={{ padding: 8 }}
            title={
              <Space>
                <span>策略实验室</span>
                <Tag color="blue">Sprint 1 · Day 3</Tag>
                {runId && <Tag>run_id: {runId.slice(0, 8)}…</Tag>}
              </Space>
            }
            extra={
              <Space>
                {!running ? (
                  <Tooltip title="提交策略到引擎子进程并轮询结果">
                    <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRun}>
                      运行
                    </Button>
                  </Tooltip>
                ) : (
                  <Button danger icon={<StopOutlined />} onClick={handleStop}>
                    停止
                  </Button>
                )}
              </Space>
            }
          >
            {(running || pct > 0) && (
              <Space style={{ width: '100%' }} direction="vertical" size={2}>
                <Progress percent={pct} status={running ? 'active' : 'normal'} size="small" showInfo />
                <Text type="secondary" style={{ fontSize: 11 }}>
                  阶段: {phaseLabel[phase] || phase} — {phaseMsg}
                </Text>
              </Space>
            )}
          </Card>

          <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
            <Card
              size="small"
              title="编辑器"
              bodyStyle={{ padding: 0, height: '100%' }}
              style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <Editor
                height="100%"
                language="python"
                theme="vs-dark"
                value={code}
                onChange={(v) => setCode(v ?? '')}
                onMount={handleEditorMount}
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  scrollBeyondLastLine: false,
                  tabSize: 4,
                  wordWrap: 'on',
                }}
              />
            </Card>

            <div style={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
              <StrategyLabResultPanel result={result} loading={running} />
            </div>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default StrategyLabPage;
