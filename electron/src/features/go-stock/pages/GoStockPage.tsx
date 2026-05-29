import React, { useState } from 'react';
import { Card, Tabs, Typography, Space } from 'antd';
import {
  GlobalOutlined,
  FileTextOutlined,
  SearchOutlined,
  FireOutlined,
  FundOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { MarketOverview } from '../components/MarketOverview';
import { NewsFeed } from '../components/NewsFeed';
import { StockLookup } from '../components/StockLookup';
import { HotStocks } from '../components/HotStocks';
import { ResearchReports } from '../components/ResearchReports';
import { FundTracker } from '../components/FundTracker';

const { Title } = Typography;

const GoStockPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('market');

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <Title level={4} style={{ marginBottom: 16 }}>
        行情资讯
      </Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'market',
            label: (
              <Space>
                <GlobalOutlined />
                市场概览
              </Space>
            ),
            children: <MarketOverview />,
          },
          {
            key: 'news',
            label: (
              <Space>
                <FileTextOutlined />
                资讯速递
              </Space>
            ),
            children: <NewsFeed />,
          },
          {
            key: 'stock',
            label: (
              <Space>
                <SearchOutlined />
                个股查询
              </Space>
            ),
            children: <StockLookup />,
          },
          {
            key: 'hot',
            label: (
              <Space>
                <FireOutlined />
                热门发现
              </Space>
            ),
            children: <HotStocks />,
          },
          {
            key: 'research',
            label: (
              <Space>
                <LineChartOutlined />
                研报中心
              </Space>
            ),
            children: <ResearchReports />,
          },
          {
            key: 'fund',
            label: (
              <Space>
                <FundOutlined />
                基金追踪
              </Space>
            ),
            children: <FundTracker />,
          },
        ]}
      />
    </div>
  );
};

export default GoStockPage;
