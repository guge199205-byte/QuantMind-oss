import React, { useState, useEffect, useCallback } from 'react';
import { Card, List, Tag, Spin, Typography, Space, Button, Select, Badge, Tooltip } from 'antd';
import { ReloadOutlined, LinkOutlined, BulbOutlined } from '@ant-design/icons';
import { goStockService } from '../services/goStockService';
import type { Telegraph } from '../types';

const { Text, Paragraph } = Typography;

export const NewsFeed: React.FC = () => {
  const [news, setNews] = useState<Telegraph[]>([]);
  const [loading, setLoading] = useState(false);
  const [source, setSource] = useState<string>('');

  const loadNews = useCallback(async () => {
    setLoading(true);
    try {
      let data: Telegraph[];
      if (source === 'sina') {
        data = await goStockService.getSinaNews(30);
      } else if (source === 'tradingview') {
        data = await goStockService.getTradingViewNews();
      } else {
        data = await goStockService.getTelegraph(30);
      }
      setNews(data || []);
    } catch (err) {
      console.error('Failed to load news:', err);
    } finally {
      setLoading(false);
    }
  }, [source]);

  useEffect(() => {
    loadNews();
    const interval = setInterval(loadNews, 60000); // Auto-refresh every minute
    return () => clearInterval(interval);
  }, [loadNews]);

  return (
    <Card
      size="small"
      title={
        <Space>
          资讯速递
          <Badge count={news.length} style={{ backgroundColor: '#1890ff' }} />
        </Space>
      }
      extra={
        <Space>
          <Select
            value={source}
            onChange={setSource}
            size="small"
            style={{ width: 120 }}
            options={[
              { label: '财联社', value: '' },
              { label: '新浪财经', value: 'sina' },
              { label: 'TradingView', value: 'tradingview' },
            ]}
          />
          <Button
            icon={<ReloadOutlined />}
            size="small"
            onClick={loadNews}
            loading={loading}
          />
        </Space>
      }
    >
      <Spin spinning={loading}>
        <List
          dataSource={news}
          style={{ maxHeight: 'calc(100vh - 280px)', overflow: 'auto' }}
          renderItem={(item: any) => (
            <List.Item style={{ padding: '8px 0' }}>
              <div style={{ width: '100%' }}>
                <Space style={{ marginBottom: 4 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{item.time || item.dataTime || '-'}</Text>
                  {item.source && <Tag color="blue" style={{ fontSize: 11 }}>{item.source}</Tag>}
                  {item.isRed && <Tag color="red" style={{ fontSize: 11 }}>重要</Tag>}
                  {item.sentimentResult && (
                    <Tooltip title={item.sentimentResult}>
                      <BulbOutlined style={{ color: '#faad14' }} />
                    </Tooltip>
                  )}
                </Space>
                {item.title && (
                  <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 14 }}>
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noopener noreferrer">
                        {item.title} <LinkOutlined style={{ fontSize: 12 }} />
                      </a>
                    ) : (
                      item.title
                    )}
                  </div>
                )}
                <Paragraph
                  style={{ margin: 0, fontSize: 13, color: '#555' }}
                  ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                >
                  {(item.content || item.description || '').replace(/<[^>]+>/g, '')}
                </Paragraph>
              </div>
            </List.Item>
          )}
        />
      </Spin>
    </Card>
  );
};
