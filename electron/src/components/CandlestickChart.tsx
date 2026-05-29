/**
 * K线图组件
 *
 * 功能：
 * - K线图展示
 * - 技术指标叠加（MA、EMA、BOLL）
 * - 成交量柱状图
 * - 交互功能（缩放、拖动、十字光标）
 * - 响应式布局
 */

import React, { useMemo, useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin, Empty, Alert } from 'antd';
import type { EChartsOption } from 'echarts';

// K线数据类型
export interface CandleData {
  timestamp: number;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

// 技术指标类型
export interface IndicatorData {
  MA5?: number[];
  MA10?: number[];
  MA20?: number[];
  MA30?: number[];
  EMA5?: number[];
  EMA10?: number[];
  EMA20?: number[];
  BOLL_UPPER?: number[];
  BOLL_MIDDLE?: number[];
  BOLL_LOWER?: number[];
}

// 组件Props
export interface CandlestickChartProps {
  // 必填属性
  symbol: string;
  data: CandleData[];

  // 可选属性
  indicators?: IndicatorData;
  height?: number;
  showVolume?: boolean;
  showDataZoom?: boolean;
  showTooltip?: boolean;
  showGrid?: boolean;
  theme?: 'light' | 'dark';
  loading?: boolean;
  error?: Error | null;

  // 回调函数
  onDataZoom?: (start: number, end: number) => void;
  onClick?: (data: CandleData) => void;
}

/**
 * K线图组件
 */
export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  symbol,
  data,
  indicators = {},
  height = 600,
  showVolume = true,
  showDataZoom = true,
  showTooltip = true,
  showGrid = true,
  theme = 'light',
  loading = false,
  error = null,
  onDataZoom,
  onClick,
}) => {
  const [chartInstance, setChartInstance] = useState<any>(null);

  // 格式化日期
  const formatDate = (timestamp: number): string => {
    const date = new Date(timestamp);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  // 格式化时间（用于tooltip）
  const formatDateTime = (timestamp: number): string => {
    const date = new Date(timestamp);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  };

  // 准备K线数据
  const candleChartData = useMemo(() => {
    if (!data || data.length === 0) return { dates: [], values: [], volumes: [] };

    const dates = data.map(d => formatDate(d.timestamp));
    const values = data.map(d => [d.open, d.close, d.low, d.high]);
    const volumes = data.map(d => d.volume);

    return { dates, values, volumes };
  }, [data]);

  // 构建ECharts配置
  const chartOption: EChartsOption = useMemo(() => {
    const { dates, values, volumes } = candleChartData;

    // 基础配置
    const option: any = {
      backgroundColor: theme === 'dark' ? '#1f1f1f' : '#ffffff',
      animation: true,
      animationDuration: 300,

      // 标题
      title: {
        text: `${symbol} K线图`,
        left: 'center',
        textStyle: {
          color: theme === 'dark' ? '#ffffff' : '#333333',
          fontSize: 16,
          fontWeight: 'bold',
        },
      },

      // 提示框
      tooltip: showTooltip ? {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
        },
        backgroundColor: theme === 'dark' ? 'rgba(50, 50, 50, 0.9)' : 'rgba(255, 255, 255, 0.9)',
        borderColor: theme === 'dark' ? '#555' : '#ccc',
        textStyle: {
          color: theme === 'dark' ? '#ffffff' : '#333333',
        },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return '';

          const dataIndex = params[0].dataIndex;
          const candleData = data[dataIndex];

          let html = `<div style="padding: 8px;">`;
          html += `<div style="font-weight: bold; margin-bottom: 8px;">${formatDateTime(candleData.timestamp)}</div>`;
          html += `<div>开盘: ${candleData.open.toFixed(2)}</div>`;
          html += `<div>收盘: ${candleData.close.toFixed(2)}</div>`;
          html += `<div>最高: ${candleData.high.toFixed(2)}</div>`;
          html += `<div>最低: ${candleData.low.toFixed(2)}</div>`;
          html += `<div>成交量: ${(candleData.volume / 1000000).toFixed(2)}M</div>`;

          // 添加指标信息
          if (indicators.MA5 && indicators.MA5[dataIndex]) {
            html += `<div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #ddd;">`;
            if (indicators.MA5[dataIndex]) html += `<div style="color: #ec407a;">MA5: ${indicators.MA5[dataIndex].toFixed(2)}</div>`;
            if (indicators.MA10 && indicators.MA10[dataIndex]) html += `<div style="color: #ab47bc;">MA10: ${indicators.MA10[dataIndex].toFixed(2)}</div>`;
            if (indicators.MA20 && indicators.MA20[dataIndex]) html += `<div style="color: #42a5f5;">MA20: ${indicators.MA20[dataIndex].toFixed(2)}</div>`;
            if (indicators.MA30 && indicators.MA30[dataIndex]) html += `<div style="color: #66bb6a;">MA30: ${indicators.MA30[dataIndex].toFixed(2)}</div>`;
            html += `</div>`;
          }

          html += `</div>`;
          return html;
        },
      } : undefined,

      // 图例
      legend: {
        data: ['K线', ...(indicators.MA5 ? ['MA5'] : []), ...(indicators.MA10 ? ['MA10'] : []), ...(indicators.MA20 ? ['MA20'] : []), ...(indicators.MA30 ? ['MA30'] : [])],
        top: 30,
        textStyle: {
          color: theme === 'dark' ? '#ffffff' : '#333333',
        },
      },

      // 网格
      grid: [
        {
          left: '10%',
          right: '10%',
          top: showVolume ? '15%' : '18%',
          height: showVolume ? '50%' : '65%',
          show: showGrid,
          borderColor: theme === 'dark' ? '#555' : '#ddd',
        },
        ...(showVolume ? [{
          left: '10%',
          right: '10%',
          top: '70%',
          height: '15%',
          show: showGrid,
          borderColor: theme === 'dark' ? '#555' : '#ddd',
        }] : []),
      ],

      // X轴
      xAxis: [
        {
          type: 'category',
          data: dates,
          scale: true,
          boundaryGap: true,
          axisLine: {
            lineStyle: {
              color: theme === 'dark' ? '#555' : '#ccc',
            },
          },
          axisLabel: {
            color: theme === 'dark' ? '#999' : '#666',
          },
          splitLine: {
            show: false,
          },
          min: 'dataMin',
          max: 'dataMax',
        },
        ...(showVolume ? [{
          type: 'category',
          gridIndex: 1,
          data: dates,
          scale: true,
          boundaryGap: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        }] : []),
      ],

      // Y轴
      yAxis: [
        {
          scale: true,
          splitArea: {
            show: true,
          },
          axisLine: {
            lineStyle: {
              color: theme === 'dark' ? '#555' : '#ccc',
            },
          },
          axisLabel: {
            color: theme === 'dark' ? '#999' : '#666',
          },
          splitLine: {
            lineStyle: {
              color: theme === 'dark' ? '#333' : '#eee',
            },
          },
        },
        ...(showVolume ? [{
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            show: true,
            color: theme === 'dark' ? '#999' : '#666',
          },
          splitLine: {
            show: false,
          },
        }] : []),
      ],

      // 数据缩放
      dataZoom: showDataZoom ? [
        {
          type: 'inside',
          xAxisIndex: showVolume ? [0, 1] : [0],
          start: 0,
          end: 100,
        },
        {
          show: true,
          xAxisIndex: showVolume ? [0, 1] : [0],
          type: 'slider',
          top: '90%',
          start: 0,
          end: 100,
        },
      ] : undefined,

      // 系列数据
      series: [
        // K线
        {
          name: 'K线',
          type: 'candlestick',
          data: values,
          itemStyle: {
            color: '#ef5350',      // 涨
            color0: '#26a69a',     // 跌
            borderColor: '#ef5350',
            borderColor0: '#26a69a',
          },
        },

        // MA均线
        ...(indicators.MA5 ? [{
          name: 'MA5',
          type: 'line',
          data: indicators.MA5,
          smooth: true,
          lineStyle: {
            width: 1,
            color: '#ec407a',
          },
          showSymbol: false,
        }] : []),

        ...(indicators.MA10 ? [{
          name: 'MA10',
          type: 'line',
          data: indicators.MA10,
          smooth: true,
          lineStyle: {
            width: 1,
            color: '#ab47bc',
          },
          showSymbol: false,
        }] : []),

        ...(indicators.MA20 ? [{
          name: 'MA20',
          type: 'line',
          data: indicators.MA20,
          smooth: true,
          lineStyle: {
            width: 1,
            color: '#42a5f5',
          },
          showSymbol: false,
        }] : []),

        ...(indicators.MA30 ? [{
          name: 'MA30',
          type: 'line',
          data: indicators.MA30,
          smooth: true,
          lineStyle: {
            width: 1,
            color: '#66bb6a',
          },
          showSymbol: false,
        }] : []),

        // 成交量
        ...(showVolume ? [{
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes.map((vol, idx) => ({
            value: vol,
            itemStyle: {
              color: values[idx][0] <= values[idx][1] ? '#ef5350' : '#26a69a',
            },
          })),
        }] : []),
      ],
    };

    return option as EChartsOption;
  }, [symbol, candleChartData, indicators, showVolume, showDataZoom, showTooltip, showGrid, theme, data]);

  // 处理图表事件
  const onChartReady = (chart: any) => {
    setChartInstance(chart);

    // 监听dataZoom事件
    if (onDataZoom) {
      chart.on('dataZoom', (params: any) => {
        const option = chart.getOption();
        const dataZoom = option.dataZoom[0];
        onDataZoom(dataZoom.start, dataZoom.end);
      });
    }

    // 监听点击事件
    if (onClick) {
      chart.on('click', (params: any) => {
        if (params.componentType === 'series' && params.seriesType === 'candlestick') {
          const dataIndex = params.dataIndex;
          onClick(data[dataIndex]);
        }
      });
    }
  };

  // 响应数据变化
  useEffect(() => {
    if (chartInstance && data) {
      chartInstance.setOption(chartOption, true);
    }
  }, [chartInstance, data, chartOption]);

  // 加载状态
  if (loading) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" tip="加载图表数据...">
          <div style={{ width: 200, height: 40 }} />
        </Spin>
      </div>
    );
  }

  // 错误状态
  if (error) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Alert
          message="图表加载失败"
          description={error.message}
          type="error"
          showIcon
        />
      </div>
    );
  }

  // 空数据状态
  if (!data || data.length === 0) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="暂无K线数据" />
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height }}>
      <ReactECharts
        option={chartOption}
        style={{ width: '100%', height: '100%' }}
        onChartReady={onChartReady}
        notMerge={true}
        lazyUpdate={true}
        theme={theme}
      />
    </div>
  );
};

export default CandlestickChart;
