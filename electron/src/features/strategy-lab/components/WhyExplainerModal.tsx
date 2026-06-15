import React from 'react';
import { Modal, Descriptions, Tag, Typography } from 'antd';
import type { StrategyLabTradeRecord } from '../types';

const { Text, Paragraph } = Typography;

interface Props {
  trade: StrategyLabTradeRecord | null;
  onClose: () => void;
}

export const WhyExplainerModal: React.FC<Props> = ({ trade, onClose }) => {
  if (!trade) return null;
  const detailKeys = trade.detail ? Object.keys(trade.detail) : [];
  return (
    <Modal
      open
      title={
        <span>
          交易原因
          <Tag color={trade.direction === 'BUY' ? 'red' : 'green'} style={{ marginLeft: 8 }}>
            {trade.direction}
          </Tag>
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>
            {trade.symbol}@{trade.date}
          </Text>
        </span>
      }
      onCancel={onClose}
      onOk={onClose}
      footer={null}
      width={520}
    >
      <Descriptions bordered size="small" column={1}>
        <Descriptions.Item label="标的">{trade.symbol}</Descriptions.Item>
        <Descriptions.Item label="日期">{trade.date}</Descriptions.Item>
        <Descriptions.Item label="价格">{trade.price.toFixed(2)}</Descriptions.Item>
        <Descriptions.Item label="数量">{trade.qty}</Descriptions.Item>
        <Descriptions.Item label="原因">
          <Paragraph style={{ margin: 0 }} copyable={{ text: trade.reason }}>
            {trade.reason || '—'}
          </Paragraph>
        </Descriptions.Item>
        {trade.pnl !== null && trade.pnl !== undefined && (
          <Descriptions.Item label="盈亏">
            <span style={{ color: trade.pnl >= 0 ? '#cf1322' : '#3f8600' }}>
              {trade.pnl.toFixed(2)}
            </span>
          </Descriptions.Item>
        )}
        {detailKeys.length > 0 && (
          <Descriptions.Item label="附加">
            <pre
              style={{
                margin: 0,
                fontSize: 11,
                background: '#f8fafc',
                padding: 8,
                borderRadius: 4,
                maxHeight: 180,
                overflow: 'auto',
              }}
            >
              {JSON.stringify(trade.detail, null, 2)}
            </pre>
          </Descriptions.Item>
        )}
      </Descriptions>
    </Modal>
  );
};

export default WhyExplainerModal;
