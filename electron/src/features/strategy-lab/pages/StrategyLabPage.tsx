import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layout, Button, Tag, Space, message, Progress, Tooltip, Typography, Collapse, Input } from 'antd';
import { PlayCircleOutlined, StopOutlined, FileTextOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons';
import { motion } from 'framer-motion';
import Editor, { OnMount } from '@monaco-editor/react';
import { strategyLabService } from '../services/strategyLabService';
import { STRATEGY_LAB_SNIPPETS, SNIPPETS_BY_CATEGORY, CATEGORY_LABELS, type SnippetCategory } from '../components/snippets';
import type {
  StrategyLabPhase,
  StrategyLabRunResult,
} from '../types';
import StrategyLabResultPanel from '../components/StrategyLabResultPanel';
import StrategyLabAiDrawer from '../components/StrategyLabAiDrawer';
import StrategyLabShell from '../components/StrategyLabShell';

const { Content } = Layout;
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
  const [prevResult, setPrevResult] = useState<StrategyLabRunResult | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const cancelPollRef = useRef<null | (() => void)>(null);
  const editorRef = useRef<any>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [snippetQuery, setSnippetQuery] = useState('');
  const [drawnLines, setDrawnLines] = useState<Record<string, number>>({});

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
    // Stash previous successful run as the comparison baseline before kicking off a new one.
    if (result?.status === 'success') {
      setPrevResult(result);
    }
    setResult(null);
    setPct(2);
    setPhase('queued');
    setPhaseMsg('提交中…');

    try {
      const submitResp = await strategyLabService.submit({ code, drawn_lines: drawnLines });
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
  }, [code, running, stopPolling, drawnLines]);

  const handleStop = useCallback(() => {
    stopPolling();
    setRunning(false);
    setPct(0);
    setPhase('queued');
    setPhaseMsg('已取消');
    message.info('已停止状态轮询（后端任务仍可能运行至完成）');
  }, [stopPolling]);

  const sider = useMemo(() => {
    const q = snippetQuery.trim().toLowerCase();
    const matches = (s: { title: string; description: string; id: string }) =>
      !q || s.title.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.id.toLowerCase().includes(q);

    const renderSnippetItem = (item: typeof STRATEGY_LAB_SNIPPETS[0]) => (
      <div
        key={item.id}
        onClick={() => handleSnippetSelect(item.id)}
        style={{
          cursor: 'pointer',
          padding: '6px 8px',
          marginBottom: 2,
          background: activeSnippet === item.id ? '#e6f4ff' : 'transparent',
          borderRadius: 4,
          border: activeSnippet === item.id ? '1px solid #7dd3fc' : '1px solid transparent',
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 500 }}>{item.title}</div>
        <div style={{ fontSize: 10, color: '#64748b', lineHeight: 1.4 }}>{item.description}</div>
      </div>
    );

    const cats: SnippetCategory[] = ['basic', 'trend', 'reversal', 'timing', 'volume', 'cross', 'factor'];
    const items = cats.flatMap((cat) => {
      const list = SNIPPETS_BY_CATEGORY[cat].filter(matches);
      if (list.length === 0) return [];
      return [
        {
          key: cat,
          label: (
            <span style={{ fontSize: 12 }}>
              {CATEGORY_LABELS[cat]} <Tag style={{ fontSize: 10, marginLeft: 4 }}>{list.length}</Tag>
            </span>
          ),
          children: <div>{list.map(renderSnippetItem)}</div>,
        },
      ];
    });

    return (
      <div style={{ height: '100%', overflowY: 'auto' }}>
        <Title level={5} style={{ marginBottom: 8 }}>
          <FileTextOutlined /> 示例策略 <Tag color="blue" style={{ fontSize: 10 }}>{STRATEGY_LAB_SNIPPETS.length}</Tag>
        </Title>
        <Input
          allowClear
          size="small"
          placeholder="搜索示例…"
          prefix={<SearchOutlined />}
          value={snippetQuery}
          onChange={(e) => setSnippetQuery(e.target.value)}
          style={{ marginBottom: 8 }}
        />
        <Collapse
          size="small"
          ghost
          defaultActiveKey={q ? cats : ['basic', 'trend']}
          activeKey={q ? cats : undefined}
          items={items}
        />
        {items.length === 0 && (
          <Text type="secondary" style={{ fontSize: 11 }}>没有匹配的示例</Text>
        )}
        <div style={{ marginTop: 16, fontSize: 11, color: '#888' }}>
          <p>示例覆盖 7 个类别（基础 / 趋势 / 反转 / 择时 / 量价 / 横截面 / 多因子）。</p>
          <p>SDK：<code>ctx.universe / start / end / cash</code>，钩子：<code>setup / on_bar / on_universe</code>。</p>
        </div>
      </div>
    );
  }, [activeSnippet, handleSnippetSelect, snippetQuery]);

  return (
    <StrategyLabShell
      activeLabel="脚本编辑器"
      contentKey={running ? 'lab-running' : result ? 'lab-result' : 'lab-idle'}
      rightActions={
        <Space size="small">
          <Button icon={<RobotOutlined />} onClick={() => setAiOpen(true)} className="!rounded-xl">
            AI 助手
          </Button>
          {!running ? (
            <Tooltip title="提交策略到引擎子进程并轮询结果">
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRun} className="!rounded-xl">
                运行
              </Button>
            </Tooltip>
          ) : (
            <Button danger icon={<StopOutlined />} onClick={handleStop} className="!rounded-xl">
              停止
            </Button>
          )}
        </Space>
      }
    >
      <Layout style={{ height: '100%', background: 'transparent' }} hasSider>
        <div style={{ width: 260, marginRight: 12 }}>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="bg-white border border-gray-200 rounded-2xl shadow-sm h-full overflow-hidden"
          >
            <div style={{ padding: 12, height: '100%', overflowY: 'auto' }}>
              {sider}
            </div>
          </motion.div>
        </div>
        <Layout style={{ background: 'transparent' }}>
          <Content style={{ padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: 0.05 }}
              className="bg-white border border-gray-200 rounded-2xl shadow-sm px-4 py-3"
            >
              <div className="flex items-center justify-between gap-2">
                <Space size="small" wrap>
                  <span className="text-sm font-semibold text-slate-700 tracking-tight">策略运行</span>
                  <Tag color="blue" className="!rounded-full !text-[11px]">Sprint 1 · Day 19</Tag>
                  {runId && <Tag className="!rounded-full !text-[11px]">run_id: {runId.slice(0, 8)}…</Tag>}
                </Space>
                <Text type="secondary" className="!text-[11px]">
                  使用 Python SDK · 子进程沙箱 · Redis 进度
                </Text>
              </div>
              {(running || pct > 0) && (
                <div className="mt-2">
                  <Progress
                    percent={pct}
                    status={running ? 'active' : 'normal'}
                    size="small"
                    showInfo
                    strokeColor={{ from: '#3b82f6', to: '#8b5cf6' }}
                  />
                  <Text type="secondary" className="!text-[11px]">
                    阶段: {phaseLabel[phase] || phase} — {phaseMsg}
                  </Text>
                </div>
              )}
            </motion.div>

            <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: 0.1 }}
                className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden"
                style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}
              >
                <div className="px-4 py-2 border-b border-gray-100 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600 tracking-tight">编辑器</span>
                  <Text type="secondary" className="!text-[11px]">Python · Monaco · {code.split('\n').length} lines</Text>
                </div>
                <div style={{ flex: 1, minHeight: 0 }}>
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
                      fontFamily: 'JetBrains Mono, Menlo, Consolas, monospace',
                      scrollBeyondLastLine: false,
                      tabSize: 4,
                      wordWrap: 'on',
                      smoothScrolling: true,
                      cursorSmoothCaretAnimation: 'on',
                    }}
                  />
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: 0.15 }}
                style={{ flex: 1, minWidth: 0, overflow: 'auto' }}
              >
                <StrategyLabResultPanel result={result} loading={running} code={code} prevResult={prevResult} onClearPrev={() => setPrevResult(null)} drawnLines={drawnLines} onDrawnLinesChange={setDrawnLines} />
              </motion.div>
            </div>
          </Content>
        </Layout>
      </Layout>
      <StrategyLabAiDrawer
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        code={code}
        lastError={
          result?.status === 'failed'
            ? { message: result.error || '', traceback: result.error_traceback || '' }
            : null
        }
        onApplyCode={(newCode) => setCode(newCode)}
      />
    </StrategyLabShell>
  );
};

export default StrategyLabPage;
