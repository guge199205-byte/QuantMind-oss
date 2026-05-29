/**
 * 策略详情页面
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Descriptions,
  Tag,
  Spin,
  Alert,
  Button,
  Space,
  Tabs,
  Statistic,
  Row,
  Col,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  StarOutlined,
  StarFilled,
  PlayCircleOutlined,
  PauseCircleOutlined,
  DeleteOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import type { UserStrategy, StrategyStatus } from '../types';
import { userCenterService } from '../services/userCenterService';

const { TabPane } = Tabs;

const StrategyDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { strategyId } = useParams<{ strategyId: string }>();
  const [strategy, setStrategy] = useState<UserStrategy | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizeStrategy = (raw: any): UserStrategy => {
    const perf = raw?.performance_summary || {};
    return {
      id: String(raw?.id ?? raw?.strategy_id ?? ''),
      user_id: String(raw?.user_id ?? ''),
      strategy_id: String(raw?.strategy_id ?? raw?.id ?? ''),
      name: String(raw?.strategy_name ?? raw?.name ?? '未命名策略'),
      strategy_type: String(raw?.strategy_type ?? 'quantitative'),
      status: (raw?.status || 'draft') as StrategyStatus,
      is_favorite: Boolean(raw?.is_favorite),
      performance_summary: {
        total_return: Number(perf.total_return ?? 0),
        total_return_pct: Number(perf.total_return_pct ?? perf.total_return ?? 0),
        sharpe_ratio: Number(perf.sharpe_ratio ?? 0),
        max_drawdown: Number(perf.max_drawdown ?? 0),
        win_rate: Number(perf.win_rate ?? 0),
        profit_factor: Number(perf.profit_factor ?? 0),
        avg_trade_duration: Number(perf.avg_trade_duration ?? 0),
        total_trades: Number(perf.total_trades ?? 0),
      },
      notes: raw?.notes || '',
      tags: Array.isArray(raw?.tags) ? raw.tags : [],
      created_at: raw?.created_at || new Date().toISOString(),
      updated_at: raw?.updated_at || new Date().toISOString(),
    };
  };

  useEffect(() => {
    if (strategyId) {
      fetchStrategyDetail(strategyId);
    }
  }, [strategyId]);

  const fetchStrategyDetail = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await userCenterService.getStrategyDetail('', id);
      setStrategy(normalizeStrategy(data));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFavorite = async () => {
    if (!strategy) return;

    try {
      const action = strategy.is_favorite ? 'unfavorite' : 'favorite';
      await userCenterService.manageUserStrategy('', String(strategy.id), action as any);
      message.success(strategy.is_favorite ? '已取消收藏' : '已收藏');
      setStrategy({ ...strategy, is_favorite: !strategy.is_favorite });
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleToggleStatus = async () => {
    if (!strategy) return;

    try {
      const nextStatus = strategy.status === 'active' ? 'archived' : 'active';
      await userCenterService.updateStrategy('', String(strategy.id), { status: nextStatus as any });
      message.success(strategy.status === 'active' ? '已归档' : '已激活');
      fetchStrategyDetail(String(strategy.id));
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const getStatusTag = (status: StrategyStatus) => {
    const statusMap: Record<StrategyStatus, { color: string; text: string }> = {
      draft: { color: 'default', text: '草稿' },
      repository: { color: 'blue', text: '仓库' },
      live_trading: { color: 'green', text: '实盘中' },
      active: { color: 'green', text: '激活' },
      inactive: { color: 'default', text: '未激活' },
      paused: { color: 'orange', text: '暂停' },
      archived: { color: 'gray', text: '归档' },
      backtesting: { color: 'blue', text: '回测中' },
    };
    const config = statusMap[status] || { color: 'default', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="加载中...">
          <div style={{ height: 100 }} />
        </Spin>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Alert message="错误" description={error} type="error" showIcon />
        <Button
          type="primary"
          style={{ marginTop: 16 }}
          onClick={() => navigate('/user-center?tab=strategies')}
        >
          返回策略列表
        </Button>
      </div>
    );
  }

  if (!strategy) {
    return (
      <div style={{ padding: 24 }}>
        <Alert message="提示" description="策略不存在" type="info" showIcon />
      </div>
    );
  }

  const performance = strategy.performance_summary;

  return (
    <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
      {/* 顶部操作栏 */}
      <div style={{ marginBottom: 24 }}>
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/user-center?tab=strategies')}
          >
            返回
          </Button>
          <Button
            icon={strategy.is_favorite ? <StarFilled /> : <StarOutlined />}
            onClick={handleToggleFavorite}
          >
            {strategy.is_favorite ? '取消收藏' : '收藏'}
          </Button>
          <Button
            icon={
              strategy.status === 'active' ? <PauseCircleOutlined /> : <PlayCircleOutlined />
            }
            onClick={handleToggleStatus}
          >
            {strategy.status === 'active' ? '归档' : '激活'}
          </Button>
          <Button icon={<EditOutlined />}>编辑</Button>
          <Button icon={<DeleteOutlined />} danger>
            删除
          </Button>
        </Space>
      </div>

      {/* 策略基本信息 */}
      <Card title="策略信息" style={{ marginBottom: 24 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="策略名称">{strategy.name}</Descriptions.Item>
          <Descriptions.Item label="策略类型">{strategy.strategy_type}</Descriptions.Item>
          <Descriptions.Item label="状态">{getStatusTag(strategy.status)}</Descriptions.Item>
          <Descriptions.Item label="是否收藏">
            {strategy.is_favorite ? (
              <Tag icon={<StarFilled />} color="gold">
                已收藏
              </Tag>
            ) : (
              <Tag>未收藏</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(strategy.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {new Date(strategy.updated_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="最后回测">
            {strategy.last_backtest_date
              ? new Date(strategy.last_backtest_date).toLocaleString('zh-CN')
              : '未回测'}
          </Descriptions.Item>
          <Descriptions.Item label="标签">
            {strategy.tags && strategy.tags.length > 0 ? (
              strategy.tags.map((tag) => (
                <Tag key={tag} style={{ marginRight: 4 }}>
                  {tag}
                </Tag>
              ))
            ) : (
              <span style={{ color: '#999' }}>无</span>
            )}
          </Descriptions.Item>
          {strategy.notes && (
            <Descriptions.Item label="备注" span={2}>
              {strategy.notes}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {/* 性能指标 */}
      <Card title="性能指标" style={{ marginBottom: 24 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="总收益率"
              value={performance.total_return_pct}
              precision={2}
              suffix="%"
              valueStyle={{
                color: performance.total_return_pct >= 0 ? '#52c41a' : '#f5222d',
              }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="夏普比率"
              value={performance.sharpe_ratio}
              precision={2}
              valueStyle={{ color: performance.sharpe_ratio >= 1 ? '#52c41a' : '#ff7a45' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="最大回撤"
              value={performance.max_drawdown}
              precision={2}
              suffix="%"
              valueStyle={{ color: '#f5222d' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="胜率"
              value={performance.win_rate}
              precision={2}
              suffix="%"
              valueStyle={{ color: performance.win_rate >= 50 ? '#52c41a' : '#ff7a45' }}
            />
          </Col>
        </Row>

        <Row gutter={16} style={{ marginTop: 24 }}>
          <Col span={6}>
            <Statistic
              title="总收益"
              value={performance.total_return}
              precision={2}
              prefix="¥"
              valueStyle={{
                color: performance.total_return >= 0 ? '#52c41a' : '#f5222d',
              }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="盈亏比"
              value={performance.profit_factor}
              precision={2}
              valueStyle={{ color: performance.profit_factor >= 1 ? '#52c41a' : '#f5222d' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="平均持仓时间"
              value={performance.avg_trade_duration}
              precision={1}
              suffix="天"
            />
          </Col>
          <Col span={6}>
            <Statistic title="总交易次数" value={performance.total_trades} />
          </Col>
        </Row>
      </Card>

      {/* 详细信息Tabs */}
      <Card>
        <Tabs defaultActiveKey="backtest">
          <TabPane tab="回测记录" key="backtest">
            <Alert
              message="功能开发中"
              description="回测记录功能正在开发中，敬请期待。"
              type="info"
              showIcon
            />
          </TabPane>
          <TabPane tab="交易记录" key="trades">
            <Alert
              message="功能开发中"
              description="交易记录功能正在开发中，敬请期待。"
              type="info"
              showIcon
            />
          </TabPane>
          <TabPane tab="配置参数" key="config">
            <Alert
              message="功能开发中"
              description="配置参数功能正在开发中，敬请期待。"
              type="info"
              showIcon
            />
          </TabPane>
        </Tabs>
      </Card>
    </div>
  );
};

export default StrategyDetailPage;
