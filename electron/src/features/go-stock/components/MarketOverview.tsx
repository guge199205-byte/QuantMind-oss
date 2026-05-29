import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Tag, Spin, Typography, Space, Segmented, Statistic } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, GlobalOutlined, TrophyOutlined } from '@ant-design/icons';
import { goStockService } from '../services/goStockService';
import type { GlobalStockIndex } from '../types';

const { Title, Text } = Typography;

interface IndustryItem {
  name?: string;
  code?: string;
  changepercent?: string;
  leading?: string;
  [key: string]: any;
}

export const MarketOverview: React.FC = () => {
  const [indexes, setIndexes] = useState<GlobalStockIndex[]>([]);
  const [industryData, setIndustryData] = useState<IndustryItem[]>([]);
  const [longTigerData, setLongTigerData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('industry');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [idx, industry, lt] = await Promise.all([
        goStockService.getCachedIndexes().catch(() => []),
        goStockService.getIndustryRank('changepercent', 30).catch(() => ({})),
        goStockService.getLongTiger().catch(() => []),
      ]);
      setIndexes(Array.isArray(idx) ? idx : []);
      // Industry rank returns a map with data key
      const industryList = (industry as any)?.data || (industry as any)?.list || [];
      setIndustryData(Array.isArray(industryList) ? industryList : Array.isArray(industry) ? industry as any[] : []);
      setLongTigerData(Array.isArray(lt) ? lt : []);
    } catch (err) {
      console.error('Failed to load market data:', err);
    } finally {
      setLoading(false);
    }
  };

  const indexColumns = [
    { title: '指数', dataIndex: 'name', key: 'name', width: 150 },
    { title: '代码', dataIndex: 'code', key: 'code', width: 100 },
    {
      title: '最新价',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '涨跌幅',
      dataIndex: 'changePercent',
      key: 'changePercent',
      width: 100,
      render: (v: string) => {
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : num < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v}%</Text>;
      },
    },
    {
      title: '涨跌额',
      dataIndex: 'changeAmount',
      key: 'changeAmount',
      width: 100,
      render: (v: string) => {
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : num < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v}</Text>;
      },
    },
    { title: '地区', dataIndex: 'region', key: 'region', width: 80 },
  ];

  const industryColumns = [
    {
      title: '行业',
      key: 'name',
      width: 120,
      render: (_: any, record: any) => record.name || record.bd_name || '-',
    },
    {
      title: '涨跌幅',
      key: 'changepercent',
      width: 100,
      render: (_: any, record: any) => {
        const v = record.changepercent || record.bd_zdf;
        if (!v) return '-';
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : num < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v}%</Text>;
      },
    },
    {
      title: '领涨股',
      key: 'leading',
      width: 100,
      render: (_: any, record: any) => record.leading || record.nzg_name || '-',
    },
    {
      title: '领涨幅',
      key: 'leading_change',
      width: 100,
      render: (_: any, record: any) => {
        const v = record.leading_change || record.leadingChange || record.nzg_zdf;
        if (!v) return '-';
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : num < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v}%</Text>;
      },
    },
  ];

  const longTigerColumns = [
    {
      title: '股票',
      key: 'stockName',
      width: 100,
      render: (_: any, record: any) => record.stockName || record.name || '-',
    },
    {
      title: '代码',
      key: 'stockCode',
      width: 80,
      render: (_: any, record: any) => record.stockCode || record.code || '-',
    },
    {
      title: '涨跌幅',
      key: 'changePercent',
      width: 100,
      render: (_: any, record: any) => {
        const v = record.changePercent || record.pct_chg || '0';
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : num < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v}%</Text>;
      },
    },
    {
      title: '买入额',
      key: 'buyAmount',
      width: 120,
      render: (_: any, record: any) => {
        const v = record.buyAmount || record.buy;
        return v ? `${(parseFloat(v) / 10000).toFixed(2)}万` : '-';
      },
    },
    {
      title: '卖出额',
      key: 'sellAmount',
      width: 120,
      render: (_: any, record: any) => {
        const v = record.sellAmount || record.sell;
        return v ? `${(parseFloat(v) / 10000).toFixed(2)}万` : '-';
      },
    },
    {
      title: '净额',
      key: 'netAmount',
      width: 120,
      render: (_: any, record: any) => {
        const v = record.netAmount || record.net;
        if (!v) return '-';
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : '#3f8600';
        return <Text style={{ color }}>{(num / 10000).toFixed(2)}万</Text>;
      },
    },
  ];

  return (
    <Spin spinning={loading}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* Global Indexes */}
        <Card
          size="small"
          title={<Space><GlobalOutlined /> 全球指数</Space>}
          extra={<a onClick={loadData}>刷新</a>}
        >
          <Table
            dataSource={indexes}
            columns={indexColumns}
            rowKey="code"
            size="small"
            pagination={false}
            scroll={{ y: 300 }}
          />
        </Card>

        {/* Industry / Long Tiger */}
        <Card size="small">
          <Segmented
            value={activeTab}
            onChange={(v) => setActiveTab(v as string)}
            options={[
              { label: '行业排名', value: 'industry', icon: <TrophyOutlined /> },
              { label: '龙虎榜', value: 'longtiger' },
            ]}
            style={{ marginBottom: 16 }}
          />
          {activeTab === 'industry' ? (
            <Table
              dataSource={industryData}
              columns={industryColumns}
              rowKey={(r, i) => r.code || String(i)}
              size="small"
              pagination={false}
              scroll={{ y: 400 }}
            />
          ) : (
            <Table
              dataSource={longTigerData}
              columns={longTigerColumns}
              rowKey={(r, i) => r.ID || r.stockCode || String(i)}
              size="small"
              pagination={{ pageSize: 20 }}
              scroll={{ y: 400 }}
            />
          )}
        </Card>
      </Space>
    </Spin>
  );
};
