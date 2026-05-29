import * as echarts from 'echarts';

export interface ChartDataPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export interface PositionRatioPoint {
  name: string;
  value: number;
  ratio?: number;
  label?: string;
  color?: string;
  itemStyle?: Record<string, unknown>;
}

type ChartType = 'dailyReturn' | 'tradeCount' | 'positionRatio';

const formatDayLabel = (date: Date): string => date.toLocaleDateString('zh-CN', {
  month: '2-digit',
  day: '2-digit',
});

const getTradeCountInterval = (maxValue: number): number => {
  if (maxValue <= 5) return 1;
  const targetTicks = 5;
  const rawInterval = maxValue / targetTicks;
  
  // 使用标准的 1, 2, 5 步进逻辑计算最接近的“圆整”刻度
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawInterval)));
  const normalized = rawInterval / magnitude;
  
  let step;
  if (normalized <= 1.2) step = 1;
  else if (normalized <= 2.5) step = 2;
  else if (normalized <= 5) step = 5;
  else step = 10;
  
  return Math.max(1, step * magnitude);
};

export const getChartOption = (type: ChartType, data: ChartDataPoint[] | PositionRatioPoint[]) => {
  const safeList = Array.isArray(data) ? data : [];
  const timeSeriesData = (safeList as ChartDataPoint[]).filter(
    (item) => item && typeof item.timestamp === 'string' && typeof item.value === 'number',
  );

  const baseOption = {
    grid: { top: 30, right: 15, bottom: 30, left: 40 },
    xAxis: {
      type: 'category',
      data: timeSeriesData.map(d => {
        const date = new Date(d.timestamp);
        // 显示完整的年月日格式，确保每个日期都是唯一的
        return date.toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        });
      }),
      axisLabel: {
        fontSize: 10,
        color: '#9CA3AF',
        // 如果数据点太多，可以旋转标签避免重叠
        rotate: timeSeriesData.length > 10 ? 45 : 0
      },
      axisLine: {
        lineStyle: {
          color: '#E5E7EB'
        }
      }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: {
        fontSize: 10,
        color: '#9CA3AF'
      },
      splitLine: {
        lineStyle: {
          type: 'dashed',
          color: '#E5E7EB'
        }
      }
    },
    series: [
      {
        data: timeSeriesData.map(d => d.value),
        type: 'line',
        smooth: true,
      },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      borderColor: '#F3F4F6',
      borderWidth: 1,
      textStyle: {
        color: '#374151'
      }
    },
  };

  switch (type) {
    case 'dailyReturn':
      // 横轴直接消费 Hook 按交易日历补齐后的序列，不再按自然日重建窗口
      const dayLabels = timeSeriesData.map((item) => formatDayLabel(new Date(item.timestamp)));
      const mappedValues = timeSeriesData.map((item) => item.value);

      // 零轴上下对称，确保盈利/亏损柱体方向稳定；并做“漂亮刻度”取整
      const rawMaxAbs = Math.max(...mappedValues.map((v) => Math.abs(v)), 1);
      const paddedMaxAbs = rawMaxAbs * 1.12;
      const base = Math.pow(10, Math.floor(Math.log10(paddedMaxAbs)));
      const ratio = paddedMaxAbs / base;
      const niceFactor =
        ratio <= 1 ? 1 :
        ratio <= 2 ? 2 :
        ratio <= 5 ? 5 : 10;
      const axisAbs = niceFactor * base;

      return {
        ...baseOption,
        xAxis: {
          ...baseOption.xAxis,
          data: dayLabels,
          axisLabel: {
            fontSize: 10,
            color: '#94A3B8',
            interval: 4,
            rotate: 0,
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            lineStyle: { color: '#CBD5E1', width: 1 },
          },
        },
        yAxis: {
          ...baseOption.yAxis,
          min: -axisAbs,
          max: axisAbs,
          splitNumber: 4,
          splitLine: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            fontSize: 10,
            color: '#94A3B8',
            formatter: (value: number) => {
              if (value === 0) return '0%';
              return value > 0 ? `+${value.toFixed(1)}%` : `${value.toFixed(1)}%`;
            }
          }
        },
        grid: { top: 18, right: 12, bottom: 26, left: 48 },
        series: [
          {
            ...baseOption.series[0],
            data: mappedValues,
            type: 'bar',
            barWidth: '58%',
            barGap: '12%',
            itemStyle: {
              color: (params: any) => {
                const value = params.data;
                return value >= 0 ? '#EF4444' : '#22C55E';
              },
              borderRadius: 0
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 8,
                shadowColor: 'rgba(15, 23, 42, 0.2)',
                shadowOffsetY: 2
              }
            }
          },
        ],
        tooltip: {
          ...baseOption.tooltip,
          formatter: (params: any) => {
            const value = params[0].data;
            const time = params[0].axisValue;
            const color = value >= 0 ? '#EF4444' : '#22C55E';
            const sign = value >= 0 ? '+' : '';
            return `
              <div style="padding: 8px;">
                <div style="margin-bottom: 4px; font-weight: 500;">${time}</div>
                <div style="color: ${color}; font-weight: 600;">
                  日收益率: ${sign}${value.toFixed(2)}%
                </div>
              </div>
            `;
          }
        }
      };
    case 'tradeCount':
      // 横轴直接消费 Hook 按交易日历补齐后的最近 7 个交易日
      const labels = timeSeriesData.map((item) => formatDayLabel(new Date(item.timestamp)));
      const values = timeSeriesData.map((item) => item.value);
      const maxValue = Math.max(...values, 0);
      const interval = getTradeCountInterval(maxValue);
      const axisMax = Math.max(interval, Math.ceil(maxValue / interval) * interval);

      return {
        ...baseOption,
        title: { text: '近7日交易次数', textStyle: { fontSize: 13, fontWeight: 'normal', color: '#4B5563' }, left: 'center', top: 2 },
        grid: { top: 35, right: 12, bottom: 38, left: 48 },
        xAxis: {
          ...baseOption.xAxis,
          data: labels,
          axisLabel: {
            fontSize: 9,
            color: '#94A3B8',
            interval: 0,
            rotate: 45,
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            lineStyle: { color: '#CBD5E1', width: 1 },
          },
          boundaryGap: true,
        },
        yAxis: {
          ...baseOption.yAxis,
          type: 'value',
          scale: false,
          min: 0,
          max: axisMax,
          interval: axisMax,
          minInterval: 1,
          splitNumber: 1,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            fontSize: 10,
            color: '#94A3B8',
            formatter: (value: number) => `${Math.round(value)}`,
          },
          splitLine: {
            lineStyle: {
              type: 'dashed',
              color: '#E5E7EB',
            },
          },
        },
        series: [
          {
            ...baseOption.series[0],
            data: values,
            type: 'bar',
            color: '#3B82F6',
            itemStyle: {
              borderRadius: [4, 4, 0, 0],
            }
          },
        ],
        tooltip: {
          ...baseOption.tooltip,
          formatter: (params: any) => {
            const value = Number(params?.[0]?.data ?? 0);
            const label = params?.[0]?.axisValue ?? '--';
            return `
              <div style="padding: 8px;">
                <div style="margin-bottom: 4px; font-weight: 500;">${label}</div>
                <div style="color: #3B82F6; font-weight: 600;">
                  交易次数: ${Math.round(value)}
                </div>
              </div>
            `;
          },
        },
      };
    case 'positionRatio':
      const pieData = (safeList as PositionRatioPoint[]).map(item => ({
        value: item.value || item.ratio,
        name: item.name || item.label,
        itemStyle: item.itemStyle || { color: item.color }
      }));

      return {
        ...baseOption,
        grid: { top: 0, right: 0, bottom: 0, left: 0 },
        tooltip: {
          trigger: 'item',
          formatter: (params: any) => {
            const name = params.name || '未知';
            const value = typeof params.value === 'number' ? params.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : params.value;
            const percent = typeof params.percent === 'number' ? params.percent.toFixed(2) : '0.00';
            return `${name}: ${value} (${percent}%)`;
          }
        },
        series: [
          {
            type: 'pie',
            radius: ['25%', '50%'],
            center: ['50%', '50%'],
            startAngle: 45,
            data: pieData.length > 0 ? pieData : [
              { value: 0, name: '无持仓', itemStyle: { color: '#E5E7EB' } }
            ],
            label: {
              show: true,
              fontSize: 9,
              formatter: (params: any) => {
                const percent = typeof params.percent === 'number' ? params.percent.toFixed(2) : '0.00';
                return `${params.name}\n${percent}%`;
              },
              position: 'outside',
              distance: 12,
              align: 'center',
              verticalAlign: 'middle'
            },
            labelLine: {
              show: true,
              length: 15,
              length2: 12
            },
            avoidLabelOverlap: true,
            emphasis: {
              label: {
                show: true,
                fontSize: 12,
                fontWeight: 'bold'
              },
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            },
          },
        ],
      };

    default:
      return baseOption;
  }
};
