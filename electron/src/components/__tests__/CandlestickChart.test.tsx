/**
 * K线图组件测试
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CandlestickChart, type CandleData } from '../CandlestickChart';

// Mock ReactECharts
vi.mock('echarts-for-react', () => ({
  default: ({ option }: any) => (
    <div data-testid="echarts-mock">
      {option.title && <div data-testid="chart-title">{option.title.text}</div>}
    </div>
  ),
}));

describe('CandlestickChart', () => {
  // 测试数据
  const mockData: CandleData[] = [
    {
      timestamp: 1609459200000,
      open: 100,
      close: 105,
      high: 108,
      low: 98,
      volume: 1000000,
    },
    {
      timestamp: 1609545600000,
      open: 105,
      close: 103,
      high: 107,
      low: 102,
      volume: 1200000,
    },
    {
      timestamp: 1609632000000,
      open: 103,
      close: 110,
      high: 112,
      low: 101,
      volume: 1500000,
    },
  ];

  const mockIndicators = {
    MA5: [NaN, NaN, NaN, NaN, 102.5],
    MA10: [NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, 103.2],
  };

  describe('渲染测试', () => {
    it('应该正常渲染图表', () => {
      render(<CandlestickChart symbol="AAPL" data={mockData} />);
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该显示股票代码', () => {
      render(<CandlestickChart symbol="AAPL" data={mockData} />);
      expect(screen.getByTestId('chart-title')).toHaveTextContent('AAPL');
    });

    it('应该显示加载状态', () => {
      const { container } = render(<CandlestickChart symbol="AAPL" data={[]} loading={true} />);
      expect(container.querySelector('.ant-spin')).toBeInTheDocument();
    });

    it('应该显示错误状态', () => {
      const error = new Error('加载失败');
      render(<CandlestickChart symbol="AAPL" data={[]} error={error} />);
      expect(screen.getByText('图表加载失败')).toBeInTheDocument();
      expect(screen.getByText('加载失败')).toBeInTheDocument();
    });

    it('应该显示空数据状态', () => {
      render(<CandlestickChart symbol="AAPL" data={[]} />);
      expect(screen.getByText('暂无K线数据')).toBeInTheDocument();
    });
  });

  describe('配置测试', () => {
    it('应该使用自定义高度', () => {
      const { container } = render(
        <CandlestickChart symbol="AAPL" data={mockData} height={800} />
      );
      const chartContainer = container.firstChild as HTMLElement;
      expect(chartContainer).toHaveStyle({ height: '800px' });
    });

    it('应该支持不显示成交量', () => {
      render(<CandlestickChart symbol="AAPL" data={mockData} showVolume={false} />);
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该支持不显示数据缩放', () => {
      render(<CandlestickChart symbol="AAPL" data={mockData} showDataZoom={false} />);
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该支持深色主题', () => {
      render(<CandlestickChart symbol="AAPL" data={mockData} theme="dark" />);
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该支持浅色主题', () => {
      render(<CandlestickChart symbol="AAPL" data={mockData} theme="light" />);
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });
  });

  describe('指标测试', () => {
    it('应该支持MA指标', () => {
      render(
        <CandlestickChart
          symbol="AAPL"
          data={mockData}
          indicators={{ MA5: mockIndicators.MA5 }}
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该支持多条MA线', () => {
      render(
        <CandlestickChart
          symbol="AAPL"
          data={mockData}
          indicators={{
            MA5: mockIndicators.MA5,
            MA10: mockIndicators.MA10,
            MA20: [NaN, NaN, NaN, NaN, NaN],
          }}
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });
  });

  describe('回调测试', () => {
    it('应该支持dataZoom回调', () => {
      const onDataZoom = vi.fn();
      render(
        <CandlestickChart
          symbol="AAPL"
          data={mockData}
          onDataZoom={onDataZoom}
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该支持点击回调', () => {
      const onClick = vi.fn();
      render(
        <CandlestickChart
          symbol="AAPL"
          data={mockData}
          onClick={onClick}
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });
  });

  describe('数据处理测试', () => {
    it('应该处理单条数据', () => {
      const singleData: CandleData[] = [mockData[0]];
      render(<CandlestickChart symbol="AAPL" data={singleData} />);
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该处理大量数据', () => {
      const largeData: CandleData[] = Array.from({ length: 1000 }, (_, i) => ({
        timestamp: 1609459200000 + i * 86400000,
        open: 100 + Math.random() * 10,
        close: 100 + Math.random() * 10,
        high: 110 + Math.random() * 5,
        low: 95 + Math.random() * 5,
        volume: 1000000 + Math.random() * 500000,
      }));
      render(<CandlestickChart symbol="AAPL" data={largeData} />);
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该处理undefined数据', () => {
      render(<CandlestickChart symbol="AAPL" data={undefined as any} />);
      expect(screen.getByText('暂无K线数据')).toBeInTheDocument();
    });
  });
});
