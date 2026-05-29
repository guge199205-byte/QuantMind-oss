import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Row, Col, Typography, Spin, message, Badge, Space, Button } from 'antd';
import {
  ReloadOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import { StockSearch } from '../components/StockSearch';
import { AnalysisForm } from '../components/AnalysisForm';
import { TaskList } from '../components/TaskList';
import { ReportViewer } from '../components/ReportViewer';
import { HistoryList } from '../components/HistoryList';
import { MarketReviewCard } from '../components/MarketReviewCard';
import { dailyAnalysisService } from '../services/dailyAnalysisService';
import type { TaskInfo, TaskStatus, AnalysisResultResponse, StockSearchResult } from '../types';

const { Title, Text } = Typography;

const DailyAnalysisPage: React.FC = () => {
  // State
  const [stockCode, setStockCode] = useState('');
  const [stockName, setStockName] = useState('');
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [selectedTask, setSelectedTask] = useState<TaskInfo | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResultResponse | null>(null);
  const [marketReviewResult, setMarketReviewResult] = useState<string>('');
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [marketReviewing, setMarketReviewing] = useState(false);

  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Load tasks
  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    try {
      const resp = await dailyAnalysisService.getTaskList(undefined, 50);
      setTasks(resp.tasks || []);
    } catch (err) {
      console.error('Failed to load tasks:', err);
    } finally {
      setTasksLoading(false);
    }
  }, []);

  // Load history
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const resp = await dailyAnalysisService.getHistory({ limit: 30 });
      setHistory(resp?.reports || resp || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadTasks();
    loadHistory();
  }, [loadTasks, loadHistory]);

  // SSE connection for real-time updates
  useEffect(() => {
    try {
      const es = dailyAnalysisService.createTaskStream();
      eventSourceRef.current = es;

      es.addEventListener('task_created', () => loadTasks());
      es.addEventListener('task_started', () => loadTasks());
      es.addEventListener('task_progress', () => loadTasks());
      es.addEventListener('task_completed', () => {
        loadTasks();
        loadHistory();
      });
      es.addEventListener('task_failed', () => loadTasks());

      return () => {
        es.close();
      };
    } catch {
      // SSE not available, fall back to polling
    }
  }, [loadTasks, loadHistory]);

  // Poll for task status when a task is selected and processing
  useEffect(() => {
    if (selectedTask && (selectedTask.status === 'processing' || selectedTask.status === 'pending')) {
      const poll = async () => {
        try {
          const status = await dailyAnalysisService.getTaskStatus(selectedTask.task_id);
          setTaskStatus(status);
          if (status.status === 'completed' && status.result) {
            setAnalysisResult(status.result);
            // Update task in list
            setTasks(
              tasks.map((t) =>
                t.task_id === selectedTask.task_id
                  ? { ...t, status: 'completed' as const, progress: 100 }
                  : t,
              ),
            );
          } else if (status.status === 'failed') {
            setTasks(
              tasks.map((t) =>
                t.task_id === selectedTask.task_id
                  ? { ...t, status: 'failed' as const, error: status.error }
                  : t,
              ),
            );
          }
        } catch (err) {
          console.error('Poll error:', err);
        }
      };

      pollRef.current = setInterval(poll, 3000);
      return () => {
        if (pollRef.current) clearInterval(pollRef.current);
      };
    }
  }, [selectedTask]);

  // Handle stock selection
  const handleStockChange = useCallback((value: string, stock?: StockSearchResult) => {
    setStockCode(value);
    if (stock?.name) setStockName(stock.name);
  }, []);

  // Handle analysis trigger
  const handleAnalyze = useCallback(
    async (options: any) => {
      if (!stockCode) {
        message.warning('请先输入股票代码');
        return;
      }
      setAnalyzing(true);
      setAnalysisResult(null);
      setTaskStatus(null);
      try {
        const resp = await dailyAnalysisService.triggerAnalysis({
          stock_code: stockCode,
          stock_name: stockName || undefined,
          ...options,
          async_mode: true,
        });
        message.success(`分析任务已提交: ${resp.task_id}`);
        await loadTasks();
        // Select the new task
        const newTask: TaskInfo = {
          task_id: resp.task_id,
          stock_code: stockCode,
          stock_name: stockName,
          status: 'pending',
          progress: 0,
          message: resp.message,
          created_at: new Date().toISOString(),
        };
        setSelectedTask(newTask);
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        if (typeof detail === 'object' && detail.message) {
          message.error(detail.message);
        } else if (err?.response?.status === 409) {
          message.warning('该股票正在分析中，请稍候');
        } else {
          message.error('分析请求失败');
        }
      } finally {
        setAnalyzing(false);
      }
    },
    [stockCode, stockName, loadTasks],
  );

  // Handle market review
  const handleMarketReview = useCallback(async () => {
    setMarketReviewing(true);
    setMarketReviewResult('');
    try {
      const resp = await dailyAnalysisService.triggerMarketReview({ send_notification: false });
      message.success(resp.message);
      // Poll for result
      if (resp.task_id) {
        const checkResult = async () => {
          try {
            const status = await dailyAnalysisService.getTaskStatus(resp.task_id!);
            if (status.status === 'completed' && status.market_review_report) {
              setMarketReviewResult(status.market_review_report);
              setMarketReviewing(false);
              return;
            }
            if (status.status === 'failed') {
              message.error('大盘复盘失败');
              setMarketReviewing(false);
              return;
            }
            setTimeout(checkResult, 5000);
          } catch {
            setMarketReviewing(false);
          }
        };
        setTimeout(checkResult, 5000);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'object' && detail.message) {
        message.warning(detail.message);
      } else {
        message.error('大盘复盘请求失败');
      }
      setMarketReviewing(false);
    }
  }, []);

  // Handle task selection
  const handleTaskSelect = useCallback(async (task: TaskInfo) => {
    setSelectedTask(task);
    setAnalysisResult(null);
    setTaskStatus(null);

    if (task.status === 'completed') {
      try {
        const status = await dailyAnalysisService.getTaskStatus(task.task_id);
        setTaskStatus(status);
        if (status.result) setAnalysisResult(status.result);
        if (status.market_review_report) setMarketReviewResult(status.market_review_report);
      } catch (err) {
        console.error('Failed to load task status:', err);
      }
    }
  }, []);

  // Handle history selection
  const handleHistorySelect = useCallback(async (item: any) => {
    try {
      const detail = await dailyAnalysisService.getReportDetail(item.query_id);
      if (detail) {
        setAnalysisResult({
          query_id: item.query_id,
          stock_code: item.stock_code,
          stock_name: item.stock_name,
          report: detail,
          created_at: item.created_at || new Date().toISOString(),
        });
      }
    } catch (err) {
      console.error('Failed to load report detail:', err);
    }
  }, []);

  // Processing tasks count
  const processingCount = tasks.filter(
    (t) => t.status === 'processing' || t.status === 'pending',
  ).length;

  return (
    <div style={{ padding: '24px', height: '100%', overflow: 'auto' }}>
      <Row gutter={24} style={{ height: '100%' }}>
        {/* Left Panel */}
        <Col xs={24} md={7} lg={6}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {/* Stock Search */}
            <Card size="small" title="股票搜索">
              <StockSearch value={stockCode} onChange={handleStockChange} />
              {stockName && (
                <Text type="secondary" style={{ display: 'block', marginTop: 4, fontSize: 12 }}>
                  {stockName}
                </Text>
              )}
            </Card>

            {/* Analysis Form */}
            <Card size="small" title="分析配置">
              <AnalysisForm
                onAnalyze={handleAnalyze}
                onMarketReview={handleMarketReview}
                loading={analyzing || marketReviewing}
                disabled={!stockCode}
              />
            </Card>

            {/* Task List */}
            <Card
              size="small"
              title={
                <Space>
                  <span>任务列表</span>
                  {processingCount > 0 && <Badge count={processingCount} />}
                </Space>
              }
              extra={
                <Button
                  type="text"
                  icon={<ReloadOutlined />}
                  onClick={loadTasks}
                  size="small"
                />
              }
            >
              <div style={{ maxHeight: 300, overflow: 'auto' }}>
                <TaskList
                  tasks={tasks}
                  loading={tasksLoading}
                  selectedTaskId={selectedTask?.task_id}
                  onSelect={handleTaskSelect}
                />
              </div>
            </Card>

            {/* History */}
            <Card
              size="small"
              title="历史记录"
              extra={
                <Button
                  type="text"
                  icon={<ReloadOutlined />}
                  onClick={loadHistory}
                  size="small"
                />
              }
            >
              <div style={{ maxHeight: 300, overflow: 'auto' }}>
                <HistoryList
                  items={history}
                  loading={historyLoading}
                  onSelect={handleHistorySelect}
                />
              </div>
            </Card>
          </Space>
        </Col>

        {/* Right Panel */}
        <Col xs={24} md={17} lg={18}>
          {analyzing || (selectedTask && (selectedTask.status === 'processing' || selectedTask.status === 'pending')) ? (
            <Card>
              <div style={{ textAlign: 'center', padding: 60 }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Title level={5}>
                    正在分析 {selectedTask?.stock_name || selectedTask?.stock_code || stockCode}
                  </Title>
                  <Text type="secondary">
                    {taskStatus?.progress !== undefined
                      ? `进度: ${taskStatus.progress}%`
                      : '正在提交分析任务...'}
                  </Text>
                </div>
              </div>
            </Card>
          ) : analysisResult || marketReviewResult ? (
            <ReportViewer result={analysisResult || undefined} report={marketReviewResult || undefined} />
          ) : (
            <Card style={{ height: '100%' }}>
              <div style={{ textAlign: 'center', padding: '120px 0' }}>
                <BarChartOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />
                <Title level={4} style={{ color: '#8c8c8c', marginTop: 16 }}>
                  智能股票分析
                </Title>
                <Text type="secondary">
                  输入股票代码，选择分析类型，开始 AI 智能分析
                </Text>
              </div>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default DailyAnalysisPage;
