import React, { useEffect, useState } from 'react';
import { Card, Spin, Alert, Button, Row, Col, Statistic, Tag } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useMarketStore } from '../stores/market-store';
import { formatPrice, formatPercent, formatVolume, formatTime } from '../utils/format';
import { useDataRefresh } from '../hooks/useDataRefresh';

/**
 * 实时行情卡片组件属性
 */
export interface RealtimeQuoteProps {
  /** 股票代码 */
  symbol: string;
  /** 自动刷新间隔（毫秒），默认5000，设为0禁用自动刷新 */
  refreshInterval?: number;
  /** 是否显示刷新按钮 */
  showRefreshButton?: boolean;
  /** 是否显示详细信息 */
  showDetails?: boolean;
  /** 卡片样式 */
  style?: React.CSSProperties;
  /** 点击回调 */
  onClick?: () => void;
}

/**
 * 实时行情卡片组件
 * 显示单个股票的实时行情信息
 */
export const RealtimeQuote: React.FC<RealtimeQuoteProps> = ({
  symbol,
  refreshInterval = 5000,
  showRefreshButton = true,
  showDetails = true,
  style,
  onClick,
}) => {
  const { quotes, loadingQuotes, errors, fetchRealtimeQuote } = useMarketStore();
  const quote = quotes[symbol];
  const loading = loadingQuotes[symbol];
  const error = errors[symbol];

  const [priceAnimation, setPriceAnimation] = useState<'up' | 'down' | null>(null);
  const [prevPrice, setPrevPrice] = useState<number | null>(null);

  // 数据刷新
  const { refreshing, lastRefreshTime, refresh } = useDataRefresh({
    interval: refreshInterval,
    enabled: refreshInterval > 0,
    immediate: true,
    onRefresh: async () => {
      await fetchRealtimeQuote(symbol);
    },
    onError: (err) => {
      console.error(`获取${symbol}行情失败:`, err);
    },
  });

  // 价格变动动画
  useEffect(() => {
    if (quote && prevPrice !== null && quote.price !== prevPrice) {
      setPriceAnimation(quote.price > prevPrice ? 'up' : 'down');
      const timer = setTimeout(() => setPriceAnimation(null), 1000);
      return () => clearTimeout(timer);
    }
    if (quote) {
      setPrevPrice(quote.price);
    }
  }, [quote?.price]); // eslint-disable-line react-hooks/exhaustive-deps

  // 涨跌状态
  const isUp = quote && quote.change >= 0;
  const changeColor = isUp ? '#cf1322' : '#3f8600';
  const bgColor = isUp ? '#fff1f0' : '#f6ffed';

  // 加载状态
  if (loading && !quote) {
    return (
      <Card style={style}>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" tip={`加载${symbol}行情中...`}>
            <div style={{ height: 40 }} />
          </Spin>
        </div>
      </Card>
    );
  }

  // 错误状态
  if (error && !quote) {
    return (
      <Card style={style}>
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
      </Card>
    );
  }

  // 无数据
  if (!quote) {
    return (
      <Card style={style}>
        <Alert type="warning" message="暂无数据" showIcon />
      </Card>
    );
  }

  return (
    <Card
      style={{ ...style, cursor: onClick ? 'pointer' : 'default' }}
      onClick={onClick}
      hoverable={!!onClick}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 'bold' }}>{symbol}</h3>
          {lastRefreshTime && (
            <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
              <ClockCircleOutlined /> {formatTime(lastRefreshTime)}
            </div>
          )}
        </div>
        {showRefreshButton && (
          <Button
            icon={<ReloadOutlined spin={refreshing} />}
            onClick={(e) => {
              e.stopPropagation();
              refresh();
            }}
            loading={refreshing}
            size="small"
          />
        )}
      </div>

      {/* 价格信息 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <div
            style={{
              fontSize: 32,
              fontWeight: 'bold',
              color: changeColor,
              transition: 'all 0.3s',
              transform: priceAnimation === 'up' ? 'scale(1.1)' : priceAnimation === 'down' ? 'scale(0.9)' : 'scale(1)',
            }}
          >
            ¥{formatPrice(quote.price)}
          </div>
        </Col>
        <Col span={12} style={{ textAlign: 'right' }}>
          <div style={{ marginBottom: 8 }}>
            <Tag
              color={isUp ? 'red' : 'green'}
              icon={isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              style={{ fontSize: 16, padding: '4px 12px' }}
            >
              {quote.change >= 0 ? '+' : ''}
              {formatPrice(quote.change)}
            </Tag>
          </div>
          <div>
            <Tag
              color={isUp ? 'red' : 'green'}
              style={{ fontSize: 14, padding: '2px 8px' }}
            >
              {formatPercent(quote.changePercent)}
            </Tag>
          </div>
        </Col>
      </Row>

      {/* 详细信息 */}
      {showDetails && (
        <div
          style={{
            backgroundColor: bgColor,
            borderRadius: 8,
            padding: 16,
          }}
        >
          <Row gutter={[16, 16]}>
            <Col span={12}>
              <Statistic
                title="开盘价"
                value={quote.open}
                precision={2}
                valueStyle={{ fontSize: 16 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="收盘价"
                value={quote.close}
                precision={2}
                valueStyle={{ fontSize: 16 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="最高价"
                value={quote.high}
                precision={2}
                valueStyle={{ fontSize: 16, color: '#cf1322' }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="最低价"
                value={quote.low}
                precision={2}
                valueStyle={{ fontSize: 16, color: '#3f8600' }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="成交量"
                value={formatVolume(quote.volume)}
                valueStyle={{ fontSize: 16 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="成交额"
                value={formatVolume(quote.amount)}
                valueStyle={{ fontSize: 16 }}
              />
            </Col>
          </Row>
        </div>
      )}
    </Card>
  );
};

export default RealtimeQuote;
