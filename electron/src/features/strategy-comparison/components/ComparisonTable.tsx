/**
 * 策略对比表格组件
 * Strategy Comparison Table
 *
 * 展示多个策略的指标对比
 *
 * @author QuantMind Team
 * @date 2025-12-02
 */

import React, { useMemo } from 'react';
import { Table, Tag, Space, Tooltip } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { StrategyComparisonItem } from '../../../shared/types/strategyComparison';
import {
  getNestedValue,
  formatMetricValue,
  isBestValue,
  DEFAULT_COMPARISON_METRICS,
  type ComparisonMetric,
} from '../../../shared/types/strategyComparison';

export interface ComparisonTableProps {
  /** 对比策略列表 */
  strategies: StrategyComparisonItem[];
  /** 是否显示基础信息 */
  showBasicInfo?: boolean;
}

interface TableRow {
  key: string;
  metric: string;
  [key: string]: any; // 动态列
}

/**
 * 策略对比表格组件
 */
export const ComparisonTable: React.FC<ComparisonTableProps> = ({
  strategies,
  showBasicInfo = true,
}) => {
  // 构建表格数据
  const tableData = useMemo(() => {
    const rows: TableRow[] = [];

    // 基础信息行
    if (showBasicInfo) {
      rows.push({
        key: 'section_basic',
        metric: '基础信息',
        isSection: true,
      });

      rows.push({
        key: 'strategy_type',
        metric: '策略类型',
        ...strategies.reduce((acc, s) => {
          acc[s.strategy_id] = s.strategy_type;
          return acc;
        }, {} as Record<string, any>),
      });

      rows.push({
        key: 'market',
        metric: '适用市场',
        ...strategies.reduce((acc, s) => {
          acc[s.strategy_id] = s.basic_info.market.join('、');
          return acc;
        }, {} as Record<string, any>),
      });

      rows.push({
        key: 'style',
        metric: '交易风格',
        ...strategies.reduce((acc, s) => {
          acc[s.strategy_id] = s.basic_info.style;
          return acc;
        }, {} as Record<string, any>),
      });

      rows.push({
        key: 'source',
        metric: '来源',
        ...strategies.reduce((acc, s) => {
          acc[s.strategy_id] = s.source_label;
          return acc;
        }, {} as Record<string, any>),
      });

      rows.push({
        key: 'created_at',
        metric: '创建时间',
        ...strategies.reduce((acc, s) => {
          acc[s.strategy_id] = new Date(s.created_at).toLocaleDateString('zh-CN');
          return acc;
        }, {} as Record<string, any>),
      });
    }

    // 指标对比行
    DEFAULT_COMPARISON_METRICS.forEach((metric, index) => {
      // 如果是新维度的第一个指标，添加分组标题
      if (index === 0 || DEFAULT_COMPARISON_METRICS[index - 1].dimension !== metric.dimension) {
        const dimensionLabels: Record<string, string> = {
          return: '收益指标',
          risk: '风险指标',
          risk_adjusted: '风险调整收益',
          trading: '交易统计',
        };

        rows.push({
          key: `section_${metric.dimension}`,
          metric: dimensionLabels[metric.dimension] || metric.dimension,
          isSection: true,
        });
      }

      // 获取所有策略的该指标值
      const values = strategies.map(s => getNestedValue(s, metric.key));

      // 添加指标行
      const row: TableRow = {
        key: metric.key,
        metric: metric.label,
        metricConfig: metric,
      };

      strategies.forEach((strategy, idx) => {
        const value = values[idx];
        row[strategy.strategy_id] = value;
        row[`${strategy.strategy_id}_isBest`] = isBestValue(value, values, metric.higher_is_better, metric.key);
      });

      rows.push(row);
    });

    return rows;
  }, [strategies, showBasicInfo]);

  // 构建表格列
  const columns = useMemo((): ColumnsType<TableRow> => {
    const cols: ColumnsType<TableRow> = [
      {
        title: '指标',
        dataIndex: 'metric',
        key: 'metric',
        fixed: 'left',
        width: 150,
        render: (text: string, record: TableRow) => {
          if (record.isSection) {
            return (
              <span style={{ fontWeight: 'bold', fontSize: 14 }}>
                {text}
              </span>
            );
          }
          return text;
        },
      },
    ];

    // 为每个策略添加一列
    strategies.forEach((strategy) => {
      cols.push({
        title: (
          <div>
            <div style={{ fontWeight: 500, marginBottom: 4 }}>
              {strategy.strategy_name}
            </div>
            <Tag color={strategy.source === 'personal' ? 'blue' : 'purple'} size="small">
              {strategy.source === 'personal' ? '🏠个人' : '🌐社区'}
            </Tag>
          </div>
        ),
        dataIndex: strategy.strategy_id,
        key: strategy.strategy_id,
        width: 150,
        align: 'center',
        render: (value: any, record: TableRow) => {
          // 分组标题行
          if (record.isSection) {
            return null;
          }

          // 基础信息行
          if (!record.metricConfig) {
            return <span>{value}</span>;
          }

          // 指标行
          const metric = record.metricConfig as ComparisonMetric;
          const isBest = record[`${strategy.strategy_id}_isBest`];
          const formattedValue = formatMetricValue(value, metric.format, metric.precision);

          // 判断好坏
          let color = '#595959';
          if (metric.format === 'percent') {
            if (metric.key.includes('max_drawdown') || metric.key.includes('drawdown')) {
              color = isBest ? '#52c41a' : '#f5222d';
            } else if (metric.higher_is_better) {
              color = value > 0 ? '#52c41a' : '#f5222d';
            } else {
              color = value < 0 ? '#52c41a' : '#f5222d';
            }
          }

          return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {isBest && (
                <Tooltip title="最佳表现">
                  <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
                </Tooltip>
              )}
              <span style={{ color, fontWeight: isBest ? 'bold' : 'normal' }}>
                {formattedValue}
              </span>
            </div>
          );
        },
      });
    });

    return cols;
  }, [strategies]);

  if (strategies.length === 0) {
    return <div style={{ textAlign: 'center', padding: 48, color: '#999' }}>请至少选择2个策略进行对比</div>;
  }

  return (
    <div className="comparison-table" style={{ overflowX: 'auto' }}>
      <Table
        columns={columns}
        dataSource={tableData}
        pagination={false}
        size="small"
        bordered
        scroll={{ x: 150 * (strategies.length + 1) }}
        rowClassName={(record) => {
          return record.isSection ? 'section-row' : '';
        }}
      />

      <style>{`
        .section-row {
          background-color: #fafafa;
          font-weight: bold;
        }
        .section-row td {
          border-bottom: 2px solid #d9d9d9 !important;
        }
      `}</style>
    </div>
  );
};

export default ComparisonTable;
