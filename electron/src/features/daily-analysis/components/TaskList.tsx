import React from 'react';
import { List, Tag, Progress, Typography, Empty, Spin } from 'antd';
import {
  ClockCircleOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { TaskInfo } from '../types';

const { Text } = Typography;

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: { color: 'default', icon: <ClockCircleOutlined />, label: '等待中' },
  processing: { color: 'processing', icon: <SyncOutlined spin />, label: '分析中' },
  completed: { color: 'success', icon: <CheckCircleOutlined />, label: '已完成' },
  failed: { color: 'error', icon: <CloseCircleOutlined />, label: '失败' },
};

interface TaskListProps {
  tasks: TaskInfo[];
  loading?: boolean;
  selectedTaskId?: string;
  onSelect?: (task: TaskInfo) => void;
}

export const TaskList: React.FC<TaskListProps> = ({
  tasks,
  loading,
  selectedTaskId,
  onSelect,
}) => {
  if (!tasks.length && !loading) {
    return <Empty description="暂无任务" style={{ padding: 40 }} />;
  }

  return (
    <List
      loading={loading}
      dataSource={tasks}
      size="small"
      renderItem={(task) => {
        const config = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
        return (
          <List.Item
            onClick={() => onSelect?.(task)}
            style={{
              cursor: 'pointer',
              padding: '12px 16px',
              background: selectedTaskId === task.task_id ? '#f0f7ff' : undefined,
              borderLeft: selectedTaskId === task.task_id ? '3px solid #1677ff' : '3px solid transparent',
            }}
          >
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <Text strong>{task.stock_name || task.stock_code}</Text>
                <Tag color={config.color} icon={config.icon}>
                  {config.label}
                </Tag>
              </div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {task.stock_code}
              </Text>
              {task.status === 'processing' && (
                <Progress
                  percent={task.progress}
                  size="small"
                  status="active"
                  style={{ marginTop: 4 }}
                />
              )}
              {task.message && (
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 2 }}>
                  {task.message}
                </Text>
              )}
              {task.error && (
                <Text type="danger" style={{ fontSize: 11, display: 'block', marginTop: 2 }}>
                  {task.error}
                </Text>
              )}
            </div>
          </List.Item>
        );
      }}
    />
  );
};
