import React from 'react';
import { List, Tag, Typography, Empty, Spin } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface HistoryItem {
  query_id: string;
  stock_code: string;
  stock_name?: string;
  report_type?: string;
  created_at?: string;
  sentiment_score?: number;
  operation_advice?: string;
}

interface HistoryListProps {
  items: HistoryItem[];
  loading?: boolean;
  selectedId?: string;
  onSelect?: (item: HistoryItem) => void;
}

export const HistoryList: React.FC<HistoryListProps> = ({
  items,
  loading,
  selectedId,
  onSelect,
}) => {
  if (!items.length && !loading) {
    return <Empty description="暂无历史记录" style={{ padding: 20 }} />;
  }

  return (
    <List
      loading={loading}
      dataSource={items}
      size="small"
      renderItem={(item) => (
        <List.Item
          onClick={() => onSelect?.(item)}
          style={{
            cursor: 'pointer',
            padding: '8px 12px',
            background: selectedId === item.query_id ? '#f0f7ff' : undefined,
          }}
        >
          <div style={{ width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text strong style={{ fontSize: 13 }}>
                {item.stock_name || item.stock_code}
              </Text>
              {item.report_type && (
                <Tag color="blue" style={{ fontSize: 10 }}>
                  {item.report_type}
                </Tag>
              )}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {item.stock_code}
              </Text>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}
              </Text>
            </div>
            {item.operation_advice && (
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 2 }} ellipsis>
                {item.operation_advice}
              </Text>
            )}
          </div>
        </List.Item>
      )}
    />
  );
};
