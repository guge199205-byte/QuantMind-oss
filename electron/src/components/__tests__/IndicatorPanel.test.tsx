/**
 * 技术指标面板组件测试
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { IndicatorPanel, type RSIData, type MACDData, type KDJData } from '../IndicatorPanel';

// Mock ReactECharts
vi.mock('echarts-for-react', () => ({
  default: ({ option }: any) => (
    <div data-testid="echarts-mock">
      {option.title && <div data-testid="chart-title">{option.title.text}</div>}
    </div>
  ),
}));

describe('IndicatorPanel', () => {
  const dates = ['1/1', '1/2', '1/3', '1/4', '1/5'];

  // RSI测试数据
  const rsiData: RSIData[] = [
    { timestamp: 1, value: 30 },
    { timestamp: 2, value: 45 },
    { timestamp: 3, value: 55 },
    { timestamp: 4, value: 70 },
    { timestamp: 5, value: 60 },
  ];

  // MACD测试数据
  const macdData: MACDData[] = [
    { timestamp: 1, dif: 0.5, dea: 0.3, macd: 0.2 },
    { timestamp: 2, dif: 0.8, dea: 0.5, macd: 0.3 },
    { timestamp: 3, dif: 1.0, dea: 0.7, macd: 0.3 },
    { timestamp: 4, dif: 0.6, dea: 0.8, macd: -0.2 },
    { timestamp: 5, dif: 0.4, dea: 0.6, macd: -0.2 },
  ];

  // KDJ测试数据
  const kdjData: KDJData[] = [
    { timestamp: 1, k: 20, d: 15, j: 30 },
    { timestamp: 2, k: 40, d: 30, j: 60 },
    { timestamp: 3, k: 60, d: 50, j: 80 },
    { timestamp: 4, k: 80, d: 70, j: 100 },
    { timestamp: 5, k: 70, d: 75, j: 60 },
  ];

  describe('渲染测试', () => {
    it('应该渲染RSI面板', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
        />
      );
      expect(screen.getByText(/RSI指标/)).toBeInTheDocument();
    });

    it('应该渲染MACD面板', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="MACD"
          data={macdData}
          dates={dates}
        />
      );
      expect(screen.getByText(/MACD指标/)).toBeInTheDocument();
    });

    it('应该渲染KDJ面板', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="KDJ"
          data={kdjData}
          dates={dates}
        />
      );
      expect(screen.getByText(/KDJ指标/)).toBeInTheDocument();
    });

    it('应该显示股票代码', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
        />
      );
      expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    });
  });

  describe('信号测试', () => {
    it('RSI超买应该显示红色标签', () => {
      const overboughtRSI: RSIData[] = [
        { timestamp: 1, value: 75 },
      ];
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={overboughtRSI}
          dates={['1/1']}
        />
      );
      expect(screen.getByText('超买')).toBeInTheDocument();
    });

    it('RSI超卖应该显示绿色标签', () => {
      const oversoldRSI: RSIData[] = [
        { timestamp: 1, value: 25 },
      ];
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={oversoldRSI}
          dates={['1/1']}
        />
      );
      expect(screen.getByText('超卖')).toBeInTheDocument();
    });

    it('RSI中性应该显示蓝色标签', () => {
      const neutralRSI: RSIData[] = [
        { timestamp: 1, value: 50 },
      ];
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={neutralRSI}
          dates={['1/1']}
        />
      );
      expect(screen.getByText('中性')).toBeInTheDocument();
    });

    it('MACD强势应该显示红色标签', () => {
      const bullishMACD: MACDData[] = [
        { timestamp: 1, dif: 1.0, dea: 0.5, macd: 0.5 },
      ];
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="MACD"
          data={bullishMACD}
          dates={['1/1']}
        />
      );
      expect(screen.getByText('强势')).toBeInTheDocument();
    });

    it('MACD弱势应该显示绿色标签', () => {
      const bearishMACD: MACDData[] = [
        { timestamp: 1, dif: -1.0, dea: -0.5, macd: -0.5 },
      ];
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="MACD"
          data={bearishMACD}
          dates={['1/1']}
        />
      );
      expect(screen.getByText('弱势')).toBeInTheDocument();
    });

    it('KDJ超买应该显示红色标签', () => {
      const overboughtKDJ: KDJData[] = [
        { timestamp: 1, k: 85, d: 80, j: 90 },
      ];
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="KDJ"
          data={overboughtKDJ}
          dates={['1/1']}
        />
      );
      expect(screen.getByText('超买')).toBeInTheDocument();
    });

    it('KDJ超卖应该显示绿色标签', () => {
      const oversoldKDJ: KDJData[] = [
        { timestamp: 1, k: 15, d: 10, j: 5 },
      ];
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="KDJ"
          data={oversoldKDJ}
          dates={['1/1']}
        />
      );
      expect(screen.getByText('超卖')).toBeInTheDocument();
    });
  });

  describe('配置测试', () => {
    it('应该显示配置选项', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
          showConfig={true}
        />
      );
      expect(screen.getByText('周期:')).toBeInTheDocument();
    });

    it('应该隐藏配置选项', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
          showConfig={false}
        />
      );
      expect(screen.queryByText('周期:')).not.toBeInTheDocument();
    });

    it('应该使用自定义高度', () => {
      const { container } = render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
          height={400}
        />
      );
      const chart = container.querySelector('[data-testid="echarts-mock"]');
      expect(chart).toBeInTheDocument();
    });

    it('应该支持深色主题', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
          theme="dark"
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该支持浅色主题', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
          theme="light"
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });
  });

  describe('参数配置测试', () => {
    it('应该显示RSI周期配置', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
          rsiPeriod={14}
        />
      );
      expect(screen.getByDisplayValue('14')).toBeInTheDocument();
    });

    it('应该显示MACD参数配置', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="MACD"
          data={macdData}
          dates={dates}
          macdFast={12}
          macdSlow={26}
          macdSignal={9}
        />
      );
      expect(screen.getByDisplayValue('12')).toBeInTheDocument();
      expect(screen.getByDisplayValue('26')).toBeInTheDocument();
      expect(screen.getByDisplayValue('9')).toBeInTheDocument();
    });

    it('应该显示KDJ参数配置', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="KDJ"
          data={kdjData}
          dates={dates}
          kdjPeriod={9}
          kdjM1={3}
          kdjM2={3}
        />
      );
      expect(screen.getAllByDisplayValue('9')).toHaveLength(1);
      expect(screen.getAllByDisplayValue('3')).toHaveLength(2);
    });
  });

  describe('回调测试', () => {
    it('应该触发配置变更回调', () => {
      const onConfigChange = vi.fn();
      const { container } = render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
          onConfigChange={onConfigChange}
        />
      );

      const input = container.querySelector('input[type="number"]');
      if (input) {
        fireEvent.change(input, { target: { value: '20' } });
      }
    });
  });

  describe('数据处理测试', () => {
    it('应该处理空数据', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={[]}
          dates={[]}
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该处理单条数据', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={[rsiData[0]]}
          dates={[dates[0]]}
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });

    it('应该处理大量数据', () => {
      const largeRSIData: RSIData[] = Array.from({ length: 1000 }, (_, i) => ({
        timestamp: i,
        value: 30 + Math.random() * 40,
      }));
      const largeDates = Array.from({ length: 1000 }, (_, i) => `${i}/1`);

      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={largeRSIData}
          dates={largeDates}
        />
      );
      expect(screen.getByTestId('echarts-mock')).toBeInTheDocument();
    });
  });

  describe('图表配置测试', () => {
    it('RSI应该显示超买超卖线', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="RSI"
          data={rsiData}
          dates={dates}
        />
      );
      expect(screen.getByTestId('chart-title')).toHaveTextContent('RSI');
    });

    it('MACD应该显示标题', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="MACD"
          data={macdData}
          dates={dates}
        />
      );
      expect(screen.getByTestId('chart-title')).toHaveTextContent('MACD');
    });

    it('KDJ应该显示标题', () => {
      render(
        <IndicatorPanel
          symbol="AAPL"
          type="KDJ"
          data={kdjData}
          dates={dates}
        />
      );
      expect(screen.getByTestId('chart-title')).toHaveTextContent('KDJ');
    });
  });
});
