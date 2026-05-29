import React from 'react';
import { Card, Descriptions, Tag, Typography, Tabs, Statistic, Row, Col, Divider, Empty } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
  RobotOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { AnalysisReport, AnalysisResultResponse } from '../types';

const { Text, Paragraph, Title } = Typography;

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#52c41a',
  negative: '#ff4d4f',
  neutral: '#faad14',
};

interface ReportViewerProps {
  result?: AnalysisResultResponse;
  report?: string; // market review report text
}

export const ReportViewer: React.FC<ReportViewerProps> = ({ result, report }) => {
  if (report) {
    return (
      <Card title="大盘复盘报告" size="small">
        <Paragraph style={{ whiteSpace: 'pre-wrap', maxHeight: 600, overflow: 'auto' }}>
          {report}
        </Paragraph>
      </Card>
    );
  }

  if (!result?.report) {
    return <Empty description="暂无报告" style={{ padding: 60 }} />;
  }

  const { report: r } = result;
  const sentimentColor = r.summary.sentiment_label
    ? SENTIMENT_COLORS[r.summary.sentiment_label] || '#1677ff'
    : '#1677ff';

  const sentimentIcon = (r.summary.sentiment_score ?? 0) > 0
    ? <ArrowUpOutlined />
    : (r.summary.sentiment_score ?? 0) < 0
      ? <ArrowDownOutlined />
      : <MinusOutlined />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header Card */}
      <Card size="small">
        <Row gutter={24} align="middle">
          <Col>
            <Title level={4} style={{ margin: 0 }}>
              {r.meta.stock_name}
              <Text type="secondary" style={{ marginLeft: 8, fontSize: 14 }}>
                {r.meta.stock_code}
              </Text>
            </Title>
          </Col>
          {r.meta.current_price !== undefined && (
            <Col>
              <Statistic
                title="当前价格"
                value={r.meta.current_price}
                precision={2}
                prefix="¥"
                valueStyle={{ fontSize: 20 }}
              />
            </Col>
          )}
          {r.meta.change_pct !== undefined && (
            <Col>
              <Statistic
                title="涨跌幅"
                value={r.meta.change_pct}
                precision={2}
                suffix="%"
                valueStyle={{
                  color: r.meta.change_pct > 0 ? '#cf1322' : r.meta.change_pct < 0 ? '#3f8600' : '#faad14',
                  fontSize: 20,
                }}
              />
            </Col>
          )}
          <Col flex="auto" />
          <Col>
            <div style={{ textAlign: 'right' }}>
              <div>
                <Tag color={sentimentColor} icon={sentimentIcon}>
                  {r.summary.sentiment_label || '未知'}
                </Tag>
                {r.summary.sentiment_score !== undefined && (
                  <Text type="secondary" style={{ marginLeft: 4 }}>
                    {r.summary.sentiment_score.toFixed(2)}
                  </Text>
                )}
              </div>
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  <RobotOutlined /> {r.meta.model_used || '未知模型'}
                </Text>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  <ClockCircleOutlined /> {r.meta.created_at ? new Date(r.meta.created_at).toLocaleString() : ''}
                </Text>
              </div>
            </div>
          </Col>
        </Row>
      </Card>

      {/* Tabs */}
      <Card size="small">
        <Tabs
          items={[
            {
              key: 'summary',
              label: '分析摘要',
              children: (
                <div>
                  <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                    {r.summary.analysis_summary || '暂无摘要'}
                  </Paragraph>
                  <Divider />
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="操作建议">
                      {r.summary.operation_advice || '—'}
                    </Descriptions.Item>
                    <Descriptions.Item label="趋势预测">
                      {r.summary.trend_prediction || '—'}
                    </Descriptions.Item>
                  </Descriptions>
                </div>
              ),
            },
            {
              key: 'strategy',
              label: '交易策略',
              children: r.strategy ? (
                <Descriptions column={2} size="small" bordered>
                  <Descriptions.Item label="理想买入价">{r.strategy.ideal_buy || '—'}</Descriptions.Item>
                  <Descriptions.Item label="次选买入价">{r.strategy.secondary_buy || '—'}</Descriptions.Item>
                  <Descriptions.Item label="止损价">{r.strategy.stop_loss || '—'}</Descriptions.Item>
                  <Descriptions.Item label="止盈价">{r.strategy.take_profit || '—'}</Descriptions.Item>
                </Descriptions>
              ) : (
                <Empty description="暂无策略数据" />
              ),
            },
            {
              key: 'news',
              label: '新闻资讯',
              children: (
                <Paragraph style={{ whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto' }}>
                  {r.details?.news_content || '暂无新闻数据'}
                </Paragraph>
              ),
            },
            {
              key: 'detail',
              label: '详细信息',
              children: (
                <div>
                  {r.details?.financial_report && (
                    <>
                      <Title level={5}>财务报表</Title>
                      <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                        {typeof r.details.financial_report === 'string'
                          ? r.details.financial_report
                          : JSON.stringify(r.details.financial_report, null, 2)}
                      </Paragraph>
                      <Divider />
                    </>
                  )}
                  {r.details?.dividend_metrics && (
                    <>
                      <Title level={5}>分红指标</Title>
                      <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                        {typeof r.details.dividend_metrics === 'string'
                          ? r.details.dividend_metrics
                          : JSON.stringify(r.details.dividend_metrics, null, 2)}
                      </Paragraph>
                      <Divider />
                    </>
                  )}
                  {r.details?.context_snapshot && (
                    <>
                      <Title level={5}>上下文快照</Title>
                      <Paragraph
                        style={{
                          whiteSpace: 'pre-wrap',
                          maxHeight: 300,
                          overflow: 'auto',
                          fontSize: 12,
                          fontFamily: 'monospace',
                        }}
                      >
                        {JSON.stringify(r.details.context_snapshot, null, 2)}
                      </Paragraph>
                    </>
                  )}
                  {!r.details?.financial_report && !r.details?.dividend_metrics && !r.details?.context_snapshot && (
                    <Empty description="暂无详细数据" />
                  )}
                </div>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
};
