import React from 'react';
import { Row, Col, Typography, Button, Space, Card } from 'antd';
import { CustomStockSelector } from './CustomStockSelector';
import { ArrowLeftOutlined, ArrowRightOutlined } from '@ant-design/icons';

const { Title, Paragraph } = Typography;

export const CustomStockPoolPage: React.FC<{ onNext: () => void; onBack: () => void }> = ({ onNext, onBack }) => {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', height: '100%' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={4}>自定义股票池</Title>
        <Paragraph type="secondary">
          在此步骤，您可以手动添加特定股票到您的策略池中。这些股票将与前面的选股条件结果合并。
        </Paragraph>
      </div>

      <div style={{ height: 600 }}>
         <CustomStockSelector />
      </div>

      <div style={{ marginTop: 24, textAlign: 'right' }}>
        <Space>
          <Button onClick={onBack} icon={<ArrowLeftOutlined />}>上一步</Button>
          <Button type="primary" onClick={onNext} icon={<ArrowRightOutlined />}>下一步</Button>
        </Space>
      </div>
    </div>
  );
};
