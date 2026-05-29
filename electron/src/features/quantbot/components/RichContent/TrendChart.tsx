/**
 * 趋势图表组件 - 使用 Recharts
 */

import React from 'react';
import { motion } from 'framer-motion';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

export type ChartType = 'line' | 'area' | 'bar';

export interface ChartDataPoint {
  name: string;
  [key: string]: string | number;
}

export interface ChartSeries {
  key: string;
  name: string;
  color: string;
}

export interface TrendChartProps {
  title: string;
  subtitle?: string;
  data: ChartDataPoint[];
  series: ChartSeries[];
  type?: ChartType;
  height?: number;
  xAxisKey?: string;
  showGrid?: boolean;
  showLegend?: boolean;
}

const TrendChart: React.FC<TrendChartProps> = ({
  title,
  subtitle,
  data,
  series,
  type = 'line',
  height = 300,
  xAxisKey = 'name',
  showGrid = true,
  showLegend = true,
}) => {
  const renderChart = () => {
    const commonProps = {
      data,
      margin: { top: 10, right: 30, left: 0, bottom: 0 },
    };

    const xAxis = (
      <XAxis
        dataKey={xAxisKey}
        stroke="#9ca3af"
        fontSize={12}
        tickLine={false}
      />
    );

    const yAxis = (
      <YAxis
        stroke="#9ca3af"
        fontSize={12}
        tickLine={false}
        axisLine={false}
      />
    );

    const grid = showGrid ? (
      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
    ) : null;

    const tooltip = (
      <Tooltip
        contentStyle={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
        }}
      />
    );

    const legend = showLegend ? <Legend /> : null;

    switch (type) {
      case 'area':
        return (
          <AreaChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            {series.map((s) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.2}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        );

      case 'bar':
        return (
          <BarChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            {series.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.name}
                fill={s.color}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        );

      case 'line':
      default:
        return (
          <LineChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        );
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden p-4"
    >
      {/* 标题 */}
      <div className="mb-4">
        <h3 className="text-lg font-bold text-gray-800">{title}</h3>
        {subtitle && (
          <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
        )}
      </div>

      {/* 图表 */}
      <ResponsiveContainer width="100%" height={height}>
        {renderChart()}
      </ResponsiveContainer>
    </motion.div>
  );
};

export default TrendChart;
