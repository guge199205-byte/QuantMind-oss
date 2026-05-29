import React, { useState, useEffect } from 'react';
import { Card, Button, Select, InputNumber, Space, Typography, Row, Col, Tag, Empty, message, Divider } from 'antd';
import { PlusOutlined, DeleteOutlined, InfoCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useWizardV2Store } from '../store/wizardV2Store';
import type { Condition } from '../types';
import { FACTORS, FACTORS_BY_CATEGORY } from '../factors/dictionary';

const { Text } = Typography;

// 扁平化的条件类型
interface FlatCondition {
  id: string;
  factor: string;
  operator: string;
  value: number;
}

const operators = [
  { label: '大于', value: '>' },
  { label: '大于等于', value: '>=' },
  { label: '小于', value: '<' },
  { label: '小于等于', value: '<=' },
  { label: '等于', value: '==' },
  { label: '不等于', value: '!=' },
];

// 分组下拉选项（按类别分组所有已知因子）
const groupedFactorOptions = Object.entries(FACTORS_BY_CATEGORY)
  .filter(([, items]) => items.length > 0)
  .map(([cat, items]) => ({
    label: cat,
    title: cat,
    options: items.map((f: any) => ({
      label: f.unit ? `${f.label} (${f.unit})` : f.label,
      value: f.key,
    })),
  }));

const FACTOR_META = new Map(FACTORS.map((f) => [f.key, f]));

// 预设条件组合（一键填入）
const PRESETS: { name: string; tip: string; items: Omit<FlatCondition, 'id'>[] }[] = [
  {
    name: '低估值蓝筹',
    tip: 'PE<20, PB<2, 市值>100亿',
    items: [
      { factor: 'pe', operator: '<', value: 20 },
      { factor: 'pb', operator: '<', value: 2 },
      { factor: 'market_cap', operator: '>', value: 100 },
    ],
  },
  {
    name: '高ROE成长',
    tip: 'ROE>15%, 60日涨幅>10%',
    items: [
      { factor: 'roe', operator: '>', value: 15 },
      { factor: 'return_60d', operator: '>', value: 10 },
      { factor: 'is_st', operator: '==', value: 0 },
    ],
  },
  {
    name: '小盘活跃',
    tip: '市值<100亿, 换手>3%',
    items: [
      { factor: 'market_cap', operator: '<', value: 100 },
      { factor: 'turnover_rate', operator: '>', value: 3 },
      { factor: 'is_st', operator: '==', value: 0 },
    ],
  },
  {
    name: '突破强势',
    tip: '5日>10日>20日均线, 量比>1.5',
    items: [
      { factor: 'ma_gap_5', operator: '>', value: 0 },
      { factor: 'ma_gap_20', operator: '>', value: 0 },
      { factor: 'volume_ratio_5', operator: '>', value: 1.5 },
    ],
  },
  {
    name: '超跌反弹',
    tip: 'RSI<30, 近5日收益<-5%',
    items: [
      { factor: 'rsi_14', operator: '<', value: 30 },
      { factor: 'return_5d', operator: '<', value: -5 },
    ],
  },
  {
    name: '沪深300+低PE',
    tip: 'HS300成分 且 PE<15',
    items: [
      { factor: 'idx_hs300', operator: '==', value: 1 },
      { factor: 'pe', operator: '<', value: 15 },
    ],
  },
  {
    name: 'AI算力',
    tip: 'AI概念 且 市值>50亿',
    items: [
      { factor: 'concept_ai', operator: '==', value: 1 },
      { factor: 'market_cap', operator: '>', value: 50 },
    ],
  },
  {
    name: '主力净流入',
    tip: '主力资金>0 且 涨幅>2%',
    items: [
      { factor: 'main_flow', operator: '>', value: 0 },
      { factor: 'pct_change', operator: '>', value: 2 },
    ],
  },
];

const MAX_CONDITIONS = 12;

export const SimpleLogicBuilder: React.FC<{
  onChange?: (c: Condition) => void;
}> = ({ onChange }) => {
  const { conditions, setConditions } = useWizardV2Store();

  const [flatConditions, setFlatConditions] = useState<FlatCondition[]>([]);
  const [logicOp, setLogicOp] = useState<'AND' | 'OR'>('AND');

  // 从 Store 同步初始化
  useEffect(() => {
    if (conditions && conditions.type === 'composite' && Array.isArray(conditions.children)) {
      const simple = conditions.children
        .map((c: any) => {
          if (c.type === 'numeric' && FACTOR_META.has(c.factor)) {
            return {
              id: Math.random().toString(36).slice(2),
              factor: c.factor,
              operator: c.operator,
              value: c.threshold,
            };
          }
          return null;
        })
        .filter(Boolean) as FlatCondition[];
      if (simple.length > 0) {
        setFlatConditions(simple);
        setLogicOp((conditions.op as any) === 'OR' ? 'OR' : 'AND');
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateStore = (list: FlatCondition[], op: 'AND' | 'OR' = logicOp) => {
    setFlatConditions(list);

    const composite: Condition = {
      type: 'composite',
      op,
      children: list.map((item) => ({
        type: 'numeric',
        factor: item.factor,
        operator: item.operator as any,
        threshold: item.value,
      })),
    };

    setConditions(composite);
    if (onChange) onChange(composite);
  };

  const addCondition = (preset?: Omit<FlatCondition, 'id'>) => {
    if (flatConditions.length >= MAX_CONDITIONS) {
      message.warning(`最多只能添加 ${MAX_CONDITIONS} 个筛选条件`);
      return;
    }
    const newItem: FlatCondition = {
      id: Math.random().toString(36).slice(2),
      factor: preset?.factor || 'market_cap',
      operator: preset?.operator || '>',
      value: preset?.value ?? 0,
    };
    updateStore([...flatConditions, newItem]);
  };

  const applyPreset = (preset: typeof PRESETS[number]) => {
    if (flatConditions.length > 0) {
      // 直接覆盖
    }
    const newList = preset.items.map((it) => ({
      ...it,
      id: Math.random().toString(36).slice(2),
    }));
    updateStore(newList);
    message.success(`已应用预设：${preset.name}`);
  };

  const removeCondition = (id: string) => {
    updateStore(flatConditions.filter((c) => c.id !== id));
  };

  const updateCondition = (id: string, field: keyof FlatCondition, val: any) => {
    const newList = flatConditions.map((c) => (c.id === id ? { ...c, [field]: val } : c));
    updateStore(newList);
  };

  const switchLogic = (op: 'AND' | 'OR') => {
    setLogicOp(op);
    updateStore(flatConditions, op);
  };

  const clearAll = () => {
    updateStore([]);
  };

  return (
    <div style={{ padding: 0 }}>
      {/* 预设条件组合 */}
      <div style={{ marginBottom: 16 }}>
        <Space style={{ marginBottom: 8 }} align="center">
          <ThunderboltOutlined style={{ color: '#f59e0b' }} />
          <Text strong style={{ fontSize: 13 }}>常用组合预设</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>（一键覆盖当前条件）</Text>
        </Space>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {PRESETS.map((p) => (
            <button
              key={p.name}
              onClick={() => applyPreset(p)}
              title={p.tip}
              style={{
                padding: '4px 10px',
                borderRadius: 6,
                border: '1px solid #fde68a',
                background: '#fffbeb',
                color: '#b45309',
                fontSize: 12,
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      <Divider style={{ margin: '12px 0' }} />

      {/* 逻辑关系切换 */}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Space>
          <Text strong style={{ fontSize: 13 }}>条件关系</Text>
          <Select
            value={logicOp}
            onChange={switchLogic}
            size="small"
            style={{ width: 90 }}
            options={[
              { label: 'AND (且)', value: 'AND' },
              { label: 'OR (或)', value: 'OR' },
            ]}
          />
          <Text type="secondary" style={{ fontSize: 11 }}>
            {logicOp === 'AND' ? '同时满足全部条件' : '满足任一条件即可'}
          </Text>
        </Space>
        {flatConditions.length > 0 && (
          <Button size="small" type="text" danger onClick={clearAll}>
            清空全部
          </Button>
        )}
      </div>

      {flatConditions.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<Text type="secondary">暂无筛选条件，点击下方按钮添加或选择上方预设</Text>}
          style={{ padding: '24px 0' }}
        >
          <Button type="primary" icon={<PlusOutlined />} onClick={() => addCondition()}>
            添加第一个条件
          </Button>
        </Empty>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          {flatConditions.map((item, index) => {
            const meta = FACTOR_META.get(item.factor);
            const unit = meta?.unit;
            return (
              <Card
                key={item.id}
                size="small"
                styles={{ body: { padding: 10 } }}
                variant="borderless"
                style={{ background: '#f9fafb', border: '1px solid #f0f0f0' }}
              >
                <Row gutter={8} align="middle">
                  <Col flex="32px">
                    <Tag color={logicOp === 'AND' ? 'blue' : 'purple'} style={{ margin: 0 }}>
                      {index + 1}
                    </Tag>
                  </Col>
                  <Col flex="auto">
                    <Space wrap size={6}>
                      <Select
                        value={item.factor}
                        style={{ width: 220 }}
                        size="middle"
                        onChange={(v) => updateCondition(item.id, 'factor', v)}
                        options={groupedFactorOptions as any}
                        showSearch
                        optionFilterProp="label"
                        placeholder="选择因子"
                      />
                      <Select
                        value={item.operator}
                        style={{ width: 110 }}
                        onChange={(v) => updateCondition(item.id, 'operator', v)}
                        options={operators}
                      />
                      <InputNumber
                        value={item.value}
                        style={{ width: 140 }}
                        onChange={(v) => updateCondition(item.id, 'value', v ?? 0)}
                        placeholder="数值"
                      />
                      {unit && <Text type="secondary" style={{ fontSize: 12 }}>{unit}</Text>}
                      {meta?.category && (
                        <Tag color="default" style={{ fontSize: 10, margin: 0 }}>
                          {meta.category}
                        </Tag>
                      )}
                    </Space>
                  </Col>
                  <Col flex="40px" style={{ textAlign: 'right' }}>
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => removeCondition(item.id)}
                    />
                  </Col>
                </Row>
              </Card>
            );
          })}

          <Button
            type="dashed"
            block
            icon={<PlusOutlined />}
            onClick={() => addCondition()}
            style={{ height: 40 }}
            disabled={flatConditions.length >= MAX_CONDITIONS}
          >
            {flatConditions.length >= MAX_CONDITIONS
              ? `已达到最大条件数量 (${MAX_CONDITIONS})`
              : '添加筛选条件'}
          </Button>

          <div
            style={{
              marginTop: 8,
              padding: 10,
              background: logicOp === 'AND' ? '#e6f7ff' : '#f9f0ff',
              borderRadius: 6,
              border: logicOp === 'AND' ? '1px solid #91d5ff' : '1px solid #d3adf7',
            }}
          >
            <Space align="start">
              <InfoCircleOutlined
                style={{ color: logicOp === 'AND' ? '#1890ff' : '#722ed1', marginTop: 2 }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                当前所有条件为{' '}
                <Text strong>{logicOp === 'AND' ? '且 (AND)' : '或 (OR)'}</Text>{' '}
                关系。
                {logicOp === 'AND'
                  ? '股票必须同时满足全部条件。'
                  : '股票满足任一条件即被选中（可能命中较多标的）。'}
                共 {flatConditions.length} / {MAX_CONDITIONS} 个条件。
              </Text>
            </Space>
          </div>
        </Space>
      )}
    </div>
  );
};
