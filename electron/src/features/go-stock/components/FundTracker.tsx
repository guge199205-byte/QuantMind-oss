import React, { useState, useEffect, useCallback } from 'react';
import { Card, Table, Input, Spin, Typography, Space, Button, Tag, Empty, message } from 'antd';
import { FundOutlined, SearchOutlined, StarOutlined, ReloadOutlined } from '@ant-design/icons';
import { goStockService } from '../services/goStockService';
import type { FollowedFund } from '../types';

const { Text } = Typography;
const { Search } = Input;

export const FundTracker: React.FC = () => {
  const [funds, setFunds] = useState<FollowedFund[]>([]);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchKey, setSearchKey] = useState('');

  const loadFollowedFunds = useCallback(async () => {
    setLoading(true);
    try {
      const data = await goStockService.getFollowedFunds();
      setFunds(data || []);
    } catch (err) {
      console.error('Failed to load funds:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFollowedFunds();
  }, [loadFollowedFunds]);

  const handleSearch = useCallback(async (key: string) => {
    if (!key.trim()) return;
    setSearchLoading(true);
    try {
      const data = await goStockService.getFundList(key.trim());
      setSearchResults(data || []);
    } catch (err) {
      console.error('Failed to search funds:', err);
    } finally {
      setSearchLoading(false);
    }
  }, []);

  const fundColumns = [
    {
      title: '基金代码',
      dataIndex: 'code',
      key: 'code',
      width: 100,
    },
    {
      title: '基金名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      ellipsis: true,
    },
    {
      title: '最新净值',
      dataIndex: 'netValue',
      key: 'netValue',
      width: 100,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '累计净值',
      dataIndex: 'totalNetValue',
      key: 'totalNetValue',
      width: 100,
    },
    {
      title: '日涨幅',
      dataIndex: 'dayGrowth',
      key: 'dayGrowth',
      width: 100,
      render: (v: string) => {
        if (!v) return '-';
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : num < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v}%</Text>;
      },
    },
    {
      title: '估算净值',
      dataIndex: 'estimatedValue',
      key: 'estimatedValue',
      width: 100,
    },
    {
      title: '估算涨幅',
      dataIndex: 'estimatedGrowth',
      key: 'estimatedGrowth',
      width: 100,
      render: (v: string) => {
        if (!v) return '-';
        const num = parseFloat(v);
        const color = num > 0 ? '#cf1322' : num < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v}%</Text>;
      },
    },
  ];

  const searchColumns = [
    {
      title: '基金代码',
      dataIndex: 'code',
      key: 'code',
      width: 100,
    },
    {
      title: '基金名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* Search */}
      <Card size="small" title={<><SearchOutlined /> 基金搜索</>}>
        <Search
          placeholder="输入基金代码或名称"
          value={searchKey}
          onChange={(e) => setSearchKey(e.target.value)}
          onSearch={handleSearch}
          enterButton="搜索"
          loading={searchLoading}
        />
        {searchResults.length > 0 && (
          <Table
            dataSource={searchResults}
            columns={searchColumns}
            rowKey={(r) => r.code || r.ID || ''}
            size="small"
            pagination={false}
            style={{ marginTop: 12 }}
          />
        )}
      </Card>

      {/* Followed Funds */}
      <Card
        size="small"
        title={<><StarOutlined /> 关注基金</>}
        extra={
          <Button
            icon={<ReloadOutlined />}
            size="small"
            onClick={loadFollowedFunds}
            loading={loading}
          />
        }
      >
        <Spin spinning={loading}>
          {funds.length > 0 ? (
            <Table
              dataSource={funds}
              columns={fundColumns}
              rowKey={(r) => r.code || r.ID || ''}
              size="small"
              pagination={{ pageSize: 20 }}
              scroll={{ y: 400 }}
            />
          ) : (
            <Empty description="暂无关注基金，请先搜索并关注" />
          )}
        </Spin>
      </Card>
    </Space>
  );
};
