import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Spin, Typography, Space, Segmented, Statistic, Tooltip } from 'antd';
import { FireOutlined, ThunderboltOutlined, FundOutlined, BankOutlined } from '@ant-design/icons';
import { goStockService } from '../services/goStockService';
import type { HotItem, HotEvent } from '../types';

const { Text, Paragraph } = Typography;

export const HotStocks: React.FC = () => {
  const [hotStocks, setHotStocks] = useState<HotItem[]>([]);
  const [hotEvents, setHotEvents] = useState<HotEvent[]>([]);
  const [hotTopics, setHotTopics] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('stocks');

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      switch (activeTab) {
        case 'stocks':
          const stocks = await goStockService.getHotStocks(30, 'A');
          setHotStocks(stocks || []);
          break;
        case 'events':
          const events = await goStockService.getHotEvents(30);
          setHotEvents(events || []);
          break;
        case 'topics':
          const topics = await goStockService.getHotTopics(30);
          setHotTopics(topics || []);
          break;
      }
    } catch (err) {
      console.error('Failed to load hot data:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      size="small"
      title={<><FireOutlined /> 热门发现</>}
      extra={
        <Segmented
          value={activeTab}
          onChange={(v) => setActiveTab(v as string)}
          options={[
            { label: '热股', value: 'stocks' },
            { label: '事件', value: 'events' },
            { label: '话题', value: 'topics' },
          ]}
          size="small"
        />
      }
    >
      <Spin spinning={loading}>
        {activeTab === 'stocks' && (
          <List
            dataSource={hotStocks}
            style={{ maxHeight: 'calc(100vh - 280px)', overflow: 'auto' }}
            locale={{ emptyText: '暂无热门股票数据' }}
            renderItem={(item: any, index) => (
              <List.Item style={{ padding: '6px 0' }}>
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Space>
                    <Tag color={index < 3 ? 'red' : index < 10 ? 'orange' : 'default'}>
                      {index + 1}
                    </Tag>
                    <Text strong>{item.name || item.stock_name || '-'}</Text>
                    {(item.code || item.stock_code) && <Text type="secondary">{item.code || item.stock_code}</Text>}
                  </Space>
                  {(item.value || item.current || item.percent) && (
                    <Text type="secondary">{item.value || item.current || item.percent}</Text>
                  )}
                </Space>
              </List.Item>
            )}
          />
        )}

        {activeTab === 'events' && (
          <List
            dataSource={hotEvents}
            style={{ maxHeight: 'calc(100vh - 280px)', overflow: 'auto' }}
            locale={{ emptyText: '暂无热门事件数据' }}
            renderItem={(item: any) => (
              <List.Item style={{ padding: '8px 0' }}>
                <div style={{ width: '100%' }}>
                  <Space style={{ marginBottom: 4 }}>
                    <ThunderboltOutlined style={{ color: '#faad14' }} />
                    <Text strong>{item.title || item.tag || '-'}</Text>
                  </Space>
                  {(item.content || item.description) && (
                    <Paragraph
                      style={{ margin: 0, fontSize: 13, color: '#666' }}
                      ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                    >
                      {item.content || item.description}
                    </Paragraph>
                  )}
                  <Space style={{ marginTop: 4 }}>
                    {item.url && (
                      <a href={item.url} target="_blank" rel="noopener noreferrer">
                        查看详情
                      </a>
                    )}
                    {(item.createdAt || item.created_at) && (
                      <Text type="secondary" style={{ fontSize: 12 }}>{item.createdAt || item.created_at}</Text>
                    )}
                  </Space>
                </div>
              </List.Item>
            )}
          />
        )}

        {activeTab === 'topics' && (
          <List
            dataSource={hotTopics}
            style={{ maxHeight: 'calc(100vh - 280px)', overflow: 'auto' }}
            renderItem={(item, index) => (
              <List.Item style={{ padding: '6px 0' }}>
                <Space>
                  <Tag color={index < 3 ? 'volcano' : index < 10 ? 'gold' : 'default'}>
                    {index + 1}
                  </Tag>
                  <Text>{typeof item === 'string' ? item : item.name || item.title || JSON.stringify(item)}</Text>
                </Space>
              </List.Item>
            )}
          />
        )}
      </Spin>
    </Card>
  );
};
