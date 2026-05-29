import React from 'react';
import * as echarts from 'echarts';
import ReactECharts from 'echarts-for-react';

interface EChartsChartProps {
  option: any;
  style?: React.CSSProperties;
  className?: string;
  chartRef?: React.Ref<any>;
}

export const EChartsChart: React.FC<EChartsChartProps> = ({ option, style, className, chartRef }) => {
  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: '100%', width: '100%', ...style }}
      className={className}
      notMerge={true}
      lazyUpdate={true}
      ref={chartRef as any}
    />
  );
};
