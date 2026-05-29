import React, { useState, useCallback } from 'react';
import { Card, Input, Row, Col, Table, Descriptions, Spin, Typography, Space, Select, Button, Empty } from 'antd';
import { SearchOutlined, LineChartOutlined } from '@ant-design/icons';
import { goStockService } from '../services/goStockService';
import type { StockBasic, KLineData } from '../types';

const { Text } = Typography;
const { Search } = Input;

export const StockLookup: React.FC = () => {
  const [searchKey, setSearchKey] = useState('');
  const [searchResults, setSearchResults] = useState<StockBasic[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockBasic | null>(null);
  const [realtimeData, setRealtimeData] = useState<any>(null);
  const [klineData, setKlineData] = useState<KLineData[]>([]);
  const [klineType, setKlineType] = useState('day');
  const [loading, setLoading] = useState(false);
  const [klineLoading, setKlineLoading] = useState(false);

  const handleSearch = useCallback(async (value: string) => {
    if (!value.trim()) return;
    setLoading(true);
    try {
      const results = await goStockService.searchStock(value.trim());
      setSearchResults(results || []);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelectStock = useCallback(async (stock: StockBasic) => {
    setSelectedStock(stock);
    setLoading(true);
    try {
      const code = stock.tsCode || stock.symbol || stock.name;
      const [realtime] = await Promise.all([
        goStockService.getStockRealtime(code).catch(() => []),
      ]);
      setRealtimeData(Array.isArray(realtime) && realtime.length > 0 ? realtime[0] : null);
    } catch (err) {
      console.error('Failed to load stock data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadKLine = useCallback(async () => {
    if (!selectedStock) return;
    const code = selectedStock.tsCode || selectedStock.symbol || '';
    if (!code) return;
    setKlineLoading(true);
    try {
      const data = await goStockService.getKLine(code, klineType, 120);
      setKlineData(data || []);
    } catch (err) {
      console.error('Failed to load K-line:', err);
    } finally {
      setKlineLoading(false);
    }
  }, [selectedStock, klineType]);

  const searchResultColumns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 80 },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      render: (v: string, record: StockBasic) => (
        <a onClick={() => handleSelectStock(record)}>{v}</a>
      ),
    },
    { title: '行业', dataIndex: 'industry', key: 'industry', width: 100 },
    { title: '市场', dataIndex: 'market', key: 'market', width: 60 },
    { title: '地区', dataIndex: 'area', key: 'area', width: 60 },
  ];

  const klineColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 100 },
    {
      title: '开盘',
      dataIndex: 'open',
      key: 'open',
      width: 80,
      render: (v: number) => v?.toFixed(2),
    },
    {
      title: '收盘',
      dataIndex: 'close',
      key: 'close',
      width: 80,
      render: (v: number) => v?.toFixed(2),
    },
    {
      title: '最高',
      dataIndex: 'high',
      key: 'high',
      width: 80,
      render: (v: number) => v?.toFixed(2),
    },
    {
      title: '最低',
      dataIndex: 'low',
      key: 'low',
      width: 80,
      render: (v: number) => v?.toFixed(2),
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 100,
      render: (v: number) => v ? (v / 10000).toFixed(2) + '万' : '-',
    },
    {
      title: '涨跌幅',
      dataIndex: 'changePercent',
      key: 'changePercent',
      width: 80,
      render: (v: number) => {
        if (v == null) return '-';
        const color = v > 0 ? '#cf1322' : v < 0 ? '#3f8600' : '#666';
        return <Text style={{ color }}>{v.toFixed(2)}%</Text>;
      },
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* Search */}
      <Card size="small" title="个股查询">
        <Search
          placeholder="输入股票代码或名称"
          value={searchKey}
          onChange={(e) => setSearchKey(e.target.value)}
          onSearch={handleSearch}
          enterButton={<><SearchOutlined /> 搜索</>}
          loading={loading}
        />
        {searchResults.length > 0 && (
          <Table
            dataSource={searchResults}
            columns={searchResultColumns}
            rowKey={(r) => r.tsCode || r.symbol || r.name || ''}
            size="small"
            pagination={{ pageSize: 10 }}
            style={{ marginTop: 12 }}
          />
        )}
      </Card>

      {/* Realtime Data */}
      {selectedStock && (
        <Card
          size="small"
          title={
            <Space>
              {selectedStock.name} ({selectedStock.symbol || selectedStock.tsCode})
            </Space>
          }
          loading={loading}
        >
          {realtimeData ? (
            <Descriptions size="small" column={4} bordered>
              <Descriptions.Item label="当前价">
                <Text strong style={{ fontSize: 16, color: '#cf1322' }}>
                  {realtimeData.price}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="涨跌幅">
                <Text style={{ color: realtimeData.changePercent > 0 ? '#cf1322' : '#3f8600' }}>
                  {realtimeData.changePercent?.toFixed(2)}%
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="开盘">{realtimeData.open}</Descriptions.Item>
              <Descriptions.Item label="昨收">{realtimeData.preClose}</Descriptions.Item>
              <Descriptions.Item label="最高">{realtimeData.high}</Descriptions.Item>
              <Descriptions.Item label="最低">{realtimeData.low}</Descriptions.Item>
              <Descriptions.Item label="成交量">{realtimeData.volume}</Descriptions.Item>
              <Descriptions.Item label="成交额">{realtimeData.amount}</Descriptions.Item>
            </Descriptions>
          ) : (
            <Empty description="暂无行情数据" />
          )}
        </Card>
      )}

      {/* K-Line */}
      {selectedStock && (
        <Card
          size="small"
          title={<><LineChartOutlined /> K线数据</>}
          extra={
            <Space>
              <Select
                value={klineType}
                onChange={setKlineType}
                size="small"
                style={{ width: 100 }}
                options={[
                  { label: '日K', value: 'day' },
                  { label: '周K', value: 'week' },
                  { label: '月K', value: 'month' },
                  { label: '5分钟', value: '5min' },
                  { label: '15分钟', value: '15min' },
                  { label: '30分钟', value: '30min' },
                  { label: '60分钟', value: '60min' },
                ]}
              />
              <Button size="small" onClick={loadKLine} loading={klineLoading}>
                加载K线
              </Button>
            </Space>
          }
        >
          <Spin spinning={klineLoading}>
            {klineData.length > 0 ? (
              <Table
                dataSource={klineData}
                columns={klineColumns}
                rowKey="date"
                size="small"
                pagination={{ pageSize: 30 }}
                scroll={{ y: 400 }}
              />
            ) : (
              <Empty description="点击「加载K线」查看数据" />
            )}
          </Spin>
        </Card>
      )}
    </Space>
  );
};
