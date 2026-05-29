import React from 'react';

interface SparklineChartProps {
  data: number[];
  color?: string;
  width?: number | string;
  height?: number | string;
}

export const SparklineChart: React.FC<SparklineChartProps> = ({
  data,
  color = '#3b82f6',
  width = '100%',
  height = 40,
}) => {
  if (!data || data.length === 0) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = range * 0.1;
  const adjustedMin = min - padding;
  const adjustedMax = max + padding;
  const adjustedRange = adjustedMax - adjustedMin;

  const points = data.map((val, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - ((val - adjustedMin) / adjustedRange) * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div style={{ width, height, overflow: 'visible' }}>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        style={{ width: '100%', height: '100%', display: 'block' }}
      >
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.4" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        
        {/* Fill Area */}
        <polyline
          fill={`url(#gradient-${color})`}
          points={`0,100 ${points} 100,100`}
          stroke="none"
        />
        
        {/* Main Line */}
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
          style={{ filter: `drop-shadow(0 0 4px ${color}80)` }}
        />
      </svg>
    </div>
  );
};
