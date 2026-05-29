import React, { useEffect, useMemo, useState } from 'react';
import { Table, Spin, Alert, Button, Space, Select, Input } from 'antd';
const { Option } = Select;
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useMarketStore } from '../stores/market-store';
import { MarketQuote } from '../types/market';
import { formatPrice, formatPercent, formatVolume } from '../utils/format';
import { useDataRefresh } from '../hooks/useDataRefresh';

/**
 * 股票列表组件属性
 */
export interface StockListProps {
  /** 股票代码列表 */
  symbols?: string[];
  /** 点击股票回调 */
  onSymbolClick?: (symbol: string) => void;
  /** 排序字段 */
  defaultSortBy?: 'symbol' | 'price' | 'change' | 'changePercent' | 'volume';
  /** 排序方向 */
  defaultSortOrder?: 'ascend' | 'descend';
  /** 是否显示搜索框 */
  showSearch?: boolean;
  /** 是否显示刷新按钮 */
  showRefresh?: boolean;
  /** 自动刷新间隔（毫秒），0表示不自动刷新 */
  refreshInterval?: number;
  /** 表格高度 */
  height?: number;
}

/**
 * 股票列表组件
 * 展示股票实时行情数据
 */
export const StockList: React.FC<StockListProps> = ({
  symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'],
  onSymbolClick,
  defaultSortBy = 'symbol',
  defaultSortOrder = 'ascend',
  showSearch = true,
  showRefresh = true,
  refreshInterval = 5000,
  height = 600,
}) => {
  const { quotes, loading, error, fetchMarketData } = useMarketStore();
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState(defaultSortBy);
  const [sortOrder, setSortOrder] = useState(defaultSortOrder);

  // 数据刷新
  const { refreshing, lastRefreshTime, refresh } = useDataRefresh({
    interval: refreshInterval,
    enabled: refreshInterval > 0,
    immediate: true,
    onRefresh: async () => {
      await fetchMarketData({ symbols });
    },
    onError: (err) => {
      console.error('刷新失败:', err);
    },
  });

  // 转换为数组并过滤搜索
  const quotesArray = useMemo(() => {
    const arr = Object.values(quotes);
    if (!searchText) return arr;

    const search = searchText.toLowerCase();
    return arr.filter((quote) =>
      quote.symbol.toLowerCase().includes(search)
    );
  }, [quotes, searchText]);

  // 排序数据
  const sortedQuotes = useMemo(() => {
    const sorted = [...quotesArray];
    sorted.sort((a, b) => {
      const aValue: number | string = a[sortBy as keyof MarketQuote];
      const bValue: number | string = b[sortBy as keyof MarketQuote];

      // 字符串比较
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortOrder === 'ascend'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }

      // 数字比较
      const aNum = Number(aValue);
      const bNum = Number(bValue);
      return sortOrder === 'ascend' ? aNum - bNum : bNum - aNum;
    });
    return sorted;
  }, [quotesArray, sortBy, sortOrder]);

  // 表格列定义
  const columns: ColumnsType<MarketQuote> = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      fixed: 'left',
      width: 120,
      render: (symbol: string) => (
        <a
          onClick={() => onSymbolClick?.(symbol)}
          style={{ fontWeight: 'bold', cursor: 'pointer' }}
        >
          {symbol}
        </a>
      ),
    },
    {
      title: '最新价',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      align: 'right',
      render: (price: number) => (
        <span style={{ fontWeight: 'bold' }}>{formatPrice(price)}</span>
      ),
    },
    {
      title: '涨跌额',
      dataIndex: 'change',
      key: 'change',
      width: 100,
      align: 'right',
      render: (change: number) => (
        <span
          style={{
            color: change >= 0 ? '#cf1322' : '#3f8600',
            fontWeight: 'bold',
          }}
        >
          {change >= 0 ? '+' : ''}
          {formatPrice(change)}
        </span>
      ),
    },
    {
      title: '涨跌幅',
      dataIndex: 'changePercent',
      key: 'changePercent',
      width: 100,
      align: 'right',
      render: (changePercent: number) => (
        <span
          style={{
            color: changePercent >= 0 ? '#cf1322' : '#3f8600',
            fontWeight: 'bold',
          }}
        >
          {formatPercent(changePercent)}
        </span>
      ),
    },
    {
      title: '开盘价',
      dataIndex: 'open',
      key: 'open',
      width: 100,
      align: 'right',
      render: (open: number) => formatPrice(open),
    },
    {
      title: '最高价',
      dataIndex: 'high',
      key: 'high',
      width: 100,
      align: 'right',
      render: (high: number) => formatPrice(high),
    },
    {
      title: '最低价',
      dataIndex: 'low',
      key: 'low',
      width: 100,
      align: 'right',
      render: (low: number) => formatPrice(low),
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 120,
      align: 'right',
      render: (volume: number) => formatVolume(volume),
    },
  ];

  // 加载状态
  if (loading && quotesArray.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '50px 0' }}>
        <Spin size="large" tip="加载中...">
          <div style={{ height: 100 }} />
        </Spin>
      </div>
    );
  }

  // 错误状态
  if (error && quotesArray.length === 0) {
    return (
      <Alert
        type="error"
        message="加载失败"
        description={error.message}
        showIcon
        action={
          <Button size="small" onClick={refresh}>
            重试
          </Button>
        }
      />
    );
  }

  return (
    <div>
      {/* 工具栏 */}
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          {showSearch && (
            <Input
              placeholder="搜索股票代码"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 200 }}
              allowClear
            />
          )}
          <Select
            value={sortBy}
            onChange={(value) => setSortBy(value)}
            style={{ width: 120 }}
          >
            <Option value="symbol">代码</Option>
            <Option value="price">价格</Option>
            <Option value="change">涨跌额</Option>
            <Option value="changePercent">涨跌幅</Option>
            <Option value="volume">成交量</Option>
          </Select>
          <Select
            value={sortOrder}
            onChange={(value) => setSortOrder(value)}
            style={{ width: 100 }}
          >
            <Option value="ascend">升序</Option>
            <Option value="descend">降序</Option>
          </Select>
        </Space>
        {showRefresh && (
          <Space>
            {lastRefreshTime && (
              <span style={{ color: '#999', fontSize: 12 }}>
                最后更新: {new Date(lastRefreshTime).toLocaleTimeString()}
              </span>
            )}
            <Button
              icon={<ReloadOutlined spin={refreshing} />}
              onClick={refresh}
              loading={refreshing}
            >
              刷新
            </Button>
          </Space>
        )}
      </Space>

      {/* 数据表格 */}
      <Table
        columns={columns}
        dataSource={sortedQuotes}
        rowKey="symbol"
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
        scroll={{ y: height, x: 'max-content' }}
        loading={loading}
        size="small"
      />
    </div>
  );
};

export default StockList;
