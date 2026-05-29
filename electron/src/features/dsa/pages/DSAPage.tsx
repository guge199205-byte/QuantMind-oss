import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  Spin,
  message,
  Button,
  Space,
  Input,
  Table,
  Tag,
  Modal,
  Form,
  Select,
  DatePicker,
  Tabs,
  Empty,
  List,
  Popconfirm,
  Switch,
} from 'antd';
import {
  ReloadOutlined,
  SearchOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  BarChartOutlined,
  RobotOutlined,
  SettingOutlined,
  HistoryOutlined,
  ThunderboltOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { dsaService } from '../services/dsaService';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// ─── Analysis Tab ────────────────────────────────────────────────────────────
const AnalysisTab: React.FC = () => {
  const [stockInput, setStockInput] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [tasks, setTasks] = useState<any[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [selectedResult, setSelectedResult] = useState<any>(null);
  const [resultModalOpen, setResultModalOpen] = useState(false);
  const [resultMarkdown, setResultMarkdown] = useState('');

  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    try {
      const resp = await dsaService.getTasks(undefined, 30);
      setTasks(resp.tasks || []);
    } catch {
      // ignore
    } finally {
      setTasksLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
    const timer = setInterval(loadTasks, 15000);
    return () => clearInterval(timer);
  }, [loadTasks]);

  const handleAnalyze = async () => {
    const codes = stockInput
      .split(/[,，\s\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (codes.length === 0) {
      message.warning('请输入股票代码');
      return;
    }
    setAnalyzing(true);
    try {
      const resp = await dsaService.analyze({
        stock_codes: codes,
        enable_news: true,
        enable_financial_report: true,
      });
      message.success(`分析任务已提交: ${resp.task_id || ''}`);
      setStockInput('');
      loadTasks();
    } catch (err: any) {
      message.error(`分析失败: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleViewResult = async (task: any) => {
    if (!task.result_record_id) {
      message.info('任务尚未完成');
      return;
    }
    try {
      const md = await dsaService.getHistoryMarkdown(task.result_record_id);
      setResultMarkdown(md.markdown || '无内容');
      setResultModalOpen(true);
    } catch (err: any) {
      message.error(`获取结果失败: ${err.message}`);
    }
  };

  const taskColumns = [
    {
      title: '股票',
      dataIndex: 'stock_codes',
      key: 'stock_codes',
      render: (codes: string[]) => (codes || []).join(', '),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          pending: 'default',
          running: 'processing',
          completed: 'success',
          failed: 'error',
        };
        return <Tag color={colorMap[status] || 'default'}>{status}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => (t ? dayjs(t).format('MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Button
          type="link"
          size="small"
          icon={<FileTextOutlined />}
          disabled={!record.result_record_id}
          onClick={() => handleViewResult(record)}
        >
          查看报告
        </Button>
      ),
    },
  ];

  return (
    <Row gutter={16}>
      <Col span={24}>
        <Card title="智能分析" size="small">
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <TextArea
              rows={3}
              placeholder="输入股票代码，多个用逗号或空格分隔（如：600519, 000858, 300750）"
              value={stockInput}
              onChange={(e) => setStockInput(e.target.value)}
            />
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={analyzing}
              onClick={handleAnalyze}
            >
              开始分析
            </Button>
          </Space>
        </Card>
      </Col>
      <Col span={24} style={{ marginTop: 16 }}>
        <Card
          title="分析任务"
          size="small"
          extra={
            <Button
              icon={<ReloadOutlined />}
              size="small"
              onClick={loadTasks}
              loading={tasksLoading}
            />
          }
        >
          <Table
            dataSource={tasks}
            columns={taskColumns}
            rowKey="task_id"
            size="small"
            pagination={{ pageSize: 10 }}
            loading={tasksLoading}
            locale={{ emptyText: <Empty description="暂无分析任务" /> }}
          />
        </Card>
      </Col>
      <Modal
        title="分析报告"
        open={resultModalOpen}
        onCancel={() => setResultModalOpen(false)}
        footer={null}
        width={900}
        styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}
      >
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6 }}>
          {resultMarkdown}
        </pre>
      </Modal>
    </Row>
  );
};

// ─── Market Review Tab ───────────────────────────────────────────────────────
const MarketReviewTab: React.FC = () => {
  const [reviewing, setReviewing] = useState(false);
  const [result, setResult] = useState('');

  const handleReview = async () => {
    setReviewing(true);
    try {
      const resp = await dsaService.marketReview({});
      setResult(typeof resp === 'string' ? resp : resp.report || JSON.stringify(resp, null, 2));
    } catch (err: any) {
      message.error(`市场复盘失败: ${err.message}`);
    } finally {
      setReviewing(false);
    }
  };

  return (
    <Card
      title="市场复盘"
      size="small"
      extra={
        <Button
          type="primary"
          icon={<BarChartOutlined />}
          loading={reviewing}
          onClick={handleReview}
        >
          执行复盘
        </Button>
      }
    >
      {result ? (
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6 }}>{result}</pre>
      ) : (
        <Empty description={'点击「执行复盘」开始今日市场分析'} />
      )}
    </Card>
  );
};

// ─── AI Chat Tab ─────────────────────────────────────────────────────────────
const AIChatTab: React.FC = () => {
  const [messages, setMessages] = useState<
    { role: 'user' | 'assistant'; content: string }[]
  >([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setSending(true);
    try {
      const resp = await dsaService.sendChat({
        message: userMsg,
        session_id: sessionId,
      });
      if (resp.session_id) setSessionId(resp.session_id);
      const assistantMsg =
        typeof resp.response === 'string'
          ? resp.response
          : resp.message || resp.content || JSON.stringify(resp);
      setMessages((prev) => [...prev, { role: 'assistant', content: assistantMsg }]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `错误: ${err.message}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <Card title="AI 投研助手" size="small" styles={{ body: { padding: 0 } }}>
      <div
        style={{
          height: 400,
          overflow: 'auto',
          padding: 16,
          background: '#fafafa',
        }}
      >
        {messages.length === 0 && (
          <Empty description="开始对话，询问市场行情、个股分析等问题" />
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              textAlign: msg.role === 'user' ? 'right' : 'left',
              marginBottom: 8,
            }}
          >
            <Tag color={msg.role === 'user' ? 'blue' : 'green'}>
              {msg.role === 'user' ? '我' : 'AI'}
            </Tag>
            <pre
              style={{
                display: 'inline-block',
                whiteSpace: 'pre-wrap',
                maxWidth: '80%',
                textAlign: 'left',
                margin: '4px 0',
                fontSize: 13,
              }}
            >
              {msg.content}
            </pre>
          </div>
        ))}
        {sending && (
          <div style={{ textAlign: 'left' }}>
            <Spin size="small" /> <Text type="secondary">AI 思考中...</Text>
          </div>
        )}
      </div>
      <div style={{ padding: 12, borderTop: '1px solid #f0f0f0' }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="输入问题..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handleSend}
            disabled={sending}
          />
          <Button type="primary" onClick={handleSend} loading={sending}>
            发送
          </Button>
        </Space.Compact>
      </div>
    </Card>
  );
};

// ─── History Tab ─────────────────────────────────────────────────────────────
const HistoryTab: React.FC = () => {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [detailModal, setDetailModal] = useState(false);
  const [detailMarkdown, setDetailMarkdown] = useState('');

  const loadHistory = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const resp = await dsaService.getHistory(p, 15);
      setHistory(resp.records || resp.items || []);
      setTotal(resp.total || 0);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory(page);
  }, [page, loadHistory]);

  const handleView = async (record: any) => {
    try {
      const md = await dsaService.getHistoryMarkdown(record.id || record.record_id);
      setDetailMarkdown(md.markdown || '无内容');
      setDetailModal(true);
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleDelete = async (record: any) => {
    try {
      await dsaService.deleteHistory(record.id || record.record_id);
      message.success('已删除');
      loadHistory(page);
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const columns = [
    {
      title: '股票',
      dataIndex: 'stock_codes',
      key: 'stock_codes',
      render: (codes: any) =>
        Array.isArray(codes) ? codes.join(', ') : codes || '-',
    },
    {
      title: '类型',
      dataIndex: 'analysis_type',
      key: 'analysis_type',
      render: (t: string) => t || '个股分析',
    },
    {
      title: '日期',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" onClick={() => handleView(record)}>
            查看
          </Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record)}>
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="分析历史"
        size="small"
        extra={
          <Button
            icon={<ReloadOutlined />}
            size="small"
            onClick={() => loadHistory(page)}
            loading={loading}
          />
        }
      >
        <Table
          dataSource={history}
          columns={columns}
          rowKey={(r) => r.id || r.record_id}
          size="small"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 15,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 条`,
          }}
          locale={{ emptyText: <Empty description="暂无历史记录" /> }}
        />
      </Card>
      <Modal
        title="分析报告"
        open={detailModal}
        onCancel={() => setDetailModal(false)}
        footer={null}
        width={900}
        styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}
      >
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6 }}>
          {detailMarkdown}
        </pre>
      </Modal>
    </>
  );
};

// ─── Settings Tab ────────────────────────────────────────────────────────────
const SettingsTab: React.FC = () => {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [setupStatus, setSetupStatus] = useState<any>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      dsaService.getSystemConfig().catch(() => null),
      dsaService.getSetupStatus().catch(() => null),
    ])
      .then(([cfg, status]) => {
        setConfig(cfg);
        setSetupStatus(status);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin />;

  return (
    <Row gutter={16}>
      <Col span={12}>
        <Card title="系统状态" size="small">
          {setupStatus ? (
            <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(setupStatus, null, 2)}
            </pre>
          ) : (
            <Empty description="无法获取状态" />
          )}
        </Card>
      </Col>
      <Col span={12}>
        <Card title="系统配置" size="small">
          {config ? (
            <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto' }}>
              {JSON.stringify(config, null, 2)}
            </pre>
          ) : (
            <Empty description="无法获取配置" />
          )}
        </Card>
      </Col>
    </Row>
  );
};

// ─── Main Page ───────────────────────────────────────────────────────────────
const DSAPage: React.FC = () => {
  const tabItems = [
    { key: 'analysis', label: '智能分析', children: <AnalysisTab /> },
    { key: 'market', label: '市场复盘', children: <MarketReviewTab /> },
    { key: 'chat', label: 'AI 助手', children: <AIChatTab /> },
    { key: 'history', label: '历史记录', children: <HistoryTab /> },
    { key: 'settings', label: '设置', children: <SettingsTab /> },
  ];

  return (
    <div style={{ padding: '0 8px' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          DSA 智能分析
        </Title>
        <Text type="secondary">A股自选股智能分析系统 — 每日报告、市场复盘、AI投研</Text>
      </div>
      <Tabs items={tabItems} defaultActiveKey="analysis" />
    </div>
  );
};

export default DSAPage;
