/**
 * K线图组件 - 使用 ECharts
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import ReactECharts from 'echarts-for-react';

export interface KLineData {
  date: string;
  open: number;
  close: number;
  low: number;
  high: number;
  volume?: number;
}

export interface KLineChartProps {
  title: string;
  subtitle?: string;
  data: KLineData[];
  height?: number;
}

const KLineChart: React.FC<KLineChartProps> = ({
  title,
  subtitle,
  data,
  height = 400,
}) => {
  const option = useMemo(() => {
    // 准备数据
    const dates = data.map(d => d.date);
    const ohlc = data.map(d => [d.open, d.close, d.low, d.high]);
    const volumes = data.map(d => d.volume || 0);

    return {
      animation: true,
      legend: {
        bottom: 10,
        left: 'center',
        data: ['K线', '成交量'],
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
        },
        borderWidth: 1,
        borderColor: '#ccc',
        padding: 10,
        textStyle: {
          color: '#000',
        },
        formatter: function (params: any) {
          const dataIndex = params[0].dataIndex;
          const d = data[dataIndex];
          return `
            <div style="font-size: 12px;">
              <div style="font-weight: bold; margin-bottom: 5px;">${d.date}</div>
              <div>开盘: ${d.open.toFixed(2)}</div>
              <div>收盘: ${d.close.toFixed(2)}</div>
              <div>最高: ${d.high.toFixed(2)}</div>
              <div>最低: ${d.low.toFixed(2)}</div>
              ${d.volume ? `<div>成交量: ${(d.volume / 10000).toFixed(2)}万</div>` : ''}
            </div>
          `;
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: 'all' }],
        label: {
          backgroundColor: '#777',
        },
      },
      grid: [
        {
          left: '10%',
          right: '8%',
          height: '50%',
        },
        {
          left: '10%',
          right: '8%',
          top: '70%',
          height: '15%',
        },
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: { onZero: false },
          splitLine: { show: false },
          splitNumber: 20,
          min: 'dataMin',
          max: 'dataMax',
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: { onZero: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          splitNumber: 20,
          min: 'dataMin',
          max: 'dataMax',
        },
      ],
      yAxis: [
        {
          scale: true,
          splitArea: {
            show: true,
          },
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 50,
          end: 100,
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          top: '90%',
          start: 50,
          end: 100,
        },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          itemStyle: {
            color: '#ef4444',
            color0: '#22c55e',
            borderColor: '#ef4444',
            borderColor0: '#22c55e',
          },
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          itemStyle: {
            color: function (params: any) {
              const dataIndex = params.dataIndex;
              const d = data[dataIndex];
              return d.close >= d.open ? '#ef4444' : '#22c55e';
            },
          },
        },
      ],
    };
  }, [data]);

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

      {/* K线图 */}
      <ReactECharts
        option={option}
        style={{ height: `${height}px` }}
        notMerge={true}
        lazyUpdate={true}
      />
    </motion.div>
  );
};

export default KLineChart;
