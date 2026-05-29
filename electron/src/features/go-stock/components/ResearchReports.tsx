import React, { useState, useCallback } from 'react';
import { Card, Input, List, Tag, Spin, Typography, Space, Select, Button, Empty, Tabs } from 'antd';
import { FileTextOutlined, SearchOutlined, BankOutlined } from '@ant-design/icons';
import { goStockService } from '../services/goStockService';

const { Text, Paragraph } = Typography;
const { Search } = Input;

export const ResearchReports: React.FC = () => {
  const [stockCode, setStockCode] = useState('');
  const [industryCode, setIndustryCode] = useState('');
  const [reports, setReports] = useState<any[]>([]);
  const [emResult, setEmResult] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('stock');
  const [emQuery, setEmQuery] = useState('');
  const [emType, setEmType] = useState('earnings');

  const loadStockResearch = useCallback(async () => {
    if (!stockCode.trim()) return;
    setLoading(true);
    try {
      const data = await goStockService.getStockResearch(stockCode.trim(), 30);
      setReports(data || []);
    } catch (err) {
      console.error('Failed to load research:', err);
    } finally {
      setLoading(false);
    }
  }, [stockCode]);

  const loadIndustryResearch = useCallback(async () => {
    if (!industryCode.trim()) return;
    setLoading(true);
    try {
      const data = await goStockService.getIndustryResearch(industryCode.trim(), 30);
      setReports(data || []);
    } catch (err) {
      console.error('Failed to load research:', err);
    } finally {
      setLoading(false);
    }
  }, [industryCode]);

  const loadEmData = useCallback(async () => {
    if (!emQuery.trim()) return;
    setLoading(true);
    setEmResult('');
    try {
      let result = '';
      switch (emType) {
        case 'earnings':
          result = await goStockService.getEarningsReview(emQuery);
          break;
        case 'qa':
          result = await goStockService.getFinancialQA(emQuery);
          break;
        case 'industry':
          result = await goStockService.getEmIndustryResearch(emQuery);
          break;
        case 'tracking':
          result = await goStockService.getTrackingReport(emQuery);
          break;
        case 'search':
          result = await goStockService.getFinanceSearch(emQuery);
          break;
        case 'comparable':
          result = await goStockService.getComparableCompany(emQuery);
          break;
        case 'hotspot':
          result = await goStockService.getHotspot(emQuery);
          break;
      }
      setEmResult(result);
    } catch (err) {
      console.error('Failed to load EM data:', err);
    } finally {
      setLoading(false);
    }
  }, [emQuery, emType]);

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card size="small" title={<><FileTextOutlined /> 研报中心</>}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'stock',
              label: '个股研报',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Search
                    placeholder="输入股票代码"
                    value={stockCode}
                    onChange={(e) => setStockCode(e.target.value)}
                    onSearch={loadStockResearch}
                    enterButton="查询研报"
                    loading={loading}
                  />
                  {reports.length > 0 ? (
                    <List
                      dataSource={reports}
                      style={{ maxHeight: 400, overflow: 'auto' }}
                      renderItem={(item: any) => (
                        <List.Item style={{ padding: '8px 0' }}>
                          <div style={{ width: '100%' }}>
                            <Space style={{ marginBottom: 4 }}>
                              {item.org && <Tag color="blue">{item.org}</Tag>}
                              {item.date && <Text type="secondary" style={{ fontSize: 12 }}>{item.date}</Text>}
                            </Space>
                            <div>
                              {item.url ? (
                                <a href={item.url} target="_blank" rel="noopener noreferrer">
                                  {item.title}
                                </a>
                              ) : (
                                <Text>{item.title}</Text>
                              )}
                            </div>
                            {item.author && <Text type="secondary" style={{ fontSize: 12 }}>作者: {item.author}</Text>}
                          </div>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty description="输入股票代码查询研报" />
                  )}
                </Space>
              ),
            },
            {
              key: 'industry',
              label: '行业研报',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Search
                    placeholder="输入行业代码"
                    value={industryCode}
                    onChange={(e) => setIndustryCode(e.target.value)}
                    onSearch={loadIndustryResearch}
                    enterButton="查询研报"
                    loading={loading}
                  />
                  {reports.length > 0 ? (
                    <List
                      dataSource={reports}
                      style={{ maxHeight: 400, overflow: 'auto' }}
                      renderItem={(item: any) => (
                        <List.Item style={{ padding: '8px 0' }}>
                          <div>
                            <Text strong>{item.title || JSON.stringify(item)}</Text>
                          </div>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty description="输入行业代码查询研报" />
                  )}
                </Space>
              ),
            },
            {
              key: 'em',
              label: '东财AI工具',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space style={{ width: '100%' }}>
                    <Select
                      value={emType}
                      onChange={setEmType}
                      style={{ width: 140 }}
                      options={[
                        { label: '业绩回顾', value: 'earnings' },
                        { label: '财务问答', value: 'qa' },
                        { label: '行业研究', value: 'industry' },
                        { label: '追踪报告', value: 'tracking' },
                        { label: '财务搜索', value: 'search' },
                        { label: '可比公司', value: 'comparable' },
                        { label: '热点发现', value: 'hotspot' },
                      ]}
                    />
                    <Search
                      placeholder="输入查询内容"
                      value={emQuery}
                      onChange={(e) => setEmQuery(e.target.value)}
                      onSearch={loadEmData}
                      enterButton="查询"
                      loading={loading}
                      style={{ flex: 1 }}
                    />
                  </Space>
                  {emResult ? (
                    <Card size="small" style={{ maxHeight: 500, overflow: 'auto' }}>
                      <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>
                        {emResult}
                      </pre>
                    </Card>
                  ) : (
                    <Empty description="选择类型并输入查询内容" />
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
};
