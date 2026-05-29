import React from 'react';
import { Card, Button, Typography, Spin } from 'antd';
import { LineChartOutlined, CheckCircleOutlined } from '@ant-design/icons';

const { Text, Paragraph } = Typography;

interface MarketReviewCardProps {
  onTrigger: () => void;
  loading?: boolean;
  result?: string;
}

export const MarketReviewCard: React.FC<MarketReviewCardProps> = ({
  onTrigger,
  loading,
  result,
}) => {
  if (result) {
    return (
      <Card
        size="small"
        title="大盘复盘"
        extra={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
      >
        <Paragraph
          style={{
            whiteSpace: 'pre-wrap',
            maxHeight: 300,
            overflow: 'auto',
            fontSize: 13,
          }}
        >
          {result}
        </Paragraph>
      </Card>
    );
  }

  return (
    <Card size="small" title="大盘复盘">
      <div style={{ textAlign: 'center', padding: 16 }}>
        {loading ? (
          <Spin tip="正在执行大盘复盘..." />
        ) : (
          <>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              分析今日大盘走势、板块轮动、资金流向
            </Text>
            <Button
              type="primary"
              icon={<LineChartOutlined />}
              onClick={onTrigger}
            >
              执行大盘复盘
            </Button>
          </>
        )}
      </div>
    </Card>
  );
};
