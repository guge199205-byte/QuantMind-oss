import React from 'react';

export interface ChartDataPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export interface MiniChartProps {
  data: ChartDataPoint[];
  width?: number;
  height?: number;
  color?: string;
  showGrid?: boolean;
  showAxes?: boolean;
  animated?: boolean;
  className?: string;
}

export const MiniChart: React.FC<MiniChartProps> = ({
  data,
  width = 200,
  height = 80,
  color = '#3B82F6',
  showGrid = false,
  showAxes = false,
  animated = true,
  className = ''
}) => {
  if (!data || data.length === 0) {
    return (
      <div
        className={`flex items-center justify-center ${className}`}
        style={{ width, height }}
      >
        <span className="text-xs text-gray-400">暂无数据</span>
      </div>
    );
  }

  // 计算数据范围
  const values = data.map(d => d.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueRange = maxValue - minValue || 1;

  // 生成路径点
  const points = data.map((point, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((point.value - minValue) / valueRange) * height;
    return `${x},${y}`;
  }).join(' ');

  // 生成面积路径
  const areaPath = `M 0,${height} L ${points} L ${width},${height} Z`;
  const linePath = `M ${points}`;

  return (
    <div className={`relative ${className}`} style={{ width, height }}>
      <svg width={width} height={height} className="overflow-visible">
        {/* 网格线 */}
        {showGrid && (
          <g className="opacity-20">
            {/* 水平网格线 */}
            {[0.25, 0.5, 0.75].map((ratio, i) => (
              <line
                key={`h-${i}`}
                x1={0}
                y1={height * ratio}
                x2={width}
                y2={height * ratio}
                stroke={color}
                strokeWidth="0.5"
              />
            ))}
            {/* 垂直网格线 */}
            {[0.25, 0.5, 0.75].map((ratio, i) => (
              <line
                key={`v-${i}`}
                x1={width * ratio}
                y1={0}
                x2={width * ratio}
                y2={height}
                stroke={color}
                strokeWidth="0.5"
              />
            ))}
          </g>
        )}

        {/* 面积图 */}
        <path
          d={areaPath}
          fill={color}
          fillOpacity="0.1"
          className={animated ? 'transition-all duration-300' : ''}
        />

        {/* 线图 */}
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={animated ? 'transition-all duration-300' : ''}
        />

        {/* 数据点 */}
        {data.map((point, index) => {
          const x = (index / (data.length - 1)) * width;
          const y = height - ((point.value - minValue) / valueRange) * height;

          return (
            <circle
              key={index}
              cx={x}
              cy={y}
              r="2"
              fill={color}
              className={`opacity-0 hover:opacity-100 transition-opacity ${animated ? 'duration-200' : ''}`}
            >
              <title>{`${point.label || point.timestamp}: ${point.value}`}</title>
            </circle>
          );
        })}

        {/* 坐标轴 */}
        {showAxes && (
          <g className="opacity-50">
            {/* X轴 */}
            <line
              x1={0}
              y1={height}
              x2={width}
              y2={height}
              stroke={color}
              strokeWidth="1"
            />
            {/* Y轴 */}
            <line
              x1={0}
              y1={0}
              x2={0}
              y2={height}
              stroke={color}
              strokeWidth="1"
            />
          </g>
        )}
      </svg>

      {/* 数值显示 */}
      <div className="absolute top-1 left-1 text-xs">
        <div className="text-gray-600">
          {data[data.length - 1]?.value?.toFixed(2)}
        </div>
        <div className={`text-xs ${
          data[data.length - 1]?.value > data[0]?.value ? 'text-green-600' : 'text-red-600'
        }`}>
          {data.length > 1 && (
            <>
              {data[data.length - 1]?.value > data[0]?.value ? '+' : ''}
              {((data[data.length - 1]?.value - data[0]?.value) / data[0]?.value * 100).toFixed(1)}%
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// 预设图表组件
export const TrendChart: React.FC<{ data: ChartDataPoint[]; trend: 'up' | 'down' | 'flat' }> = ({
  data,
  trend
}) => {
  const colors = {
    up: '#10B981',
    down: '#EF4444',
    flat: '#6B7280'
  };

  return (
    <MiniChart
      data={data}
      color={colors[trend]}
      width={120}
      height={40}
      animated={true}
    />
  );
};

export const PerformanceChart: React.FC<{ data: ChartDataPoint[] }> = ({ data }) => {
  return (
    <MiniChart
      data={data}
      color="#8B5CF6"
      width={150}
      height={60}
      showGrid={true}
      animated={true}
    />
  );
};
