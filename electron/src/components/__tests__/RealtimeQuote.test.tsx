import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { RealtimeQuote } from '../RealtimeQuote';
import type { MarketQuote } from '../StockList';
import { useMarketStore } from '../../stores/market-store';
import { useDataRefresh } from '../../hooks/useDataRefresh';

// Mock services
vi.mock('../../services', () => ({
  getAPIClient: vi.fn(),
}));

// Mock store
const mockFetchRealtimeQuote = vi.fn();
const mockQuote: MarketQuote = {
  symbol: 'AAPL',
  price: 150.25,
  change: 2.5,
  changePercent: 1.69,
  open: 148.0,
  high: 151.0,
  low: 147.5,
  close: 150.25,
  volume: 50000000,
  amount: 7500000000,
  timestamp: Date.now(),
};

vi.mock('../../stores/market-store', () => ({
  useMarketStore: vi.fn(() => ({
    quotes: { AAPL: mockQuote },
    loadingQuotes: {},
    errors: {},
    fetchRealtimeQuote: mockFetchRealtimeQuote,
  })),
}));

// Mock hooks
vi.mock('../../hooks/useDataRefresh', () => ({
  useDataRefresh: vi.fn(() => ({
    refreshing: false,
    lastRefreshTime: Date.now(),
    refresh: vi.fn(),
    error: null,
  })),
}));

const mockedUseMarketStore = vi.mocked(useMarketStore);
const mockedUseDataRefresh = vi.mocked(useDataRefresh);

describe('RealtimeQuote', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseMarketStore.mockReturnValue({
      quotes: { AAPL: mockQuote },
      loadingQuotes: {},
      errors: {},
      fetchRealtimeQuote: mockFetchRealtimeQuote,
    });
    mockedUseDataRefresh.mockReturnValue({
      refreshing: false,
      lastRefreshTime: Date.now(),
      refresh: vi.fn(),
      error: null,
    });
  });

  it('应该渲染股票代码', async () => {
    render(<RealtimeQuote symbol="AAPL" />);

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
  });

  it('应该显示价格', async () => {
    render(<RealtimeQuote symbol="AAPL" />);

    await waitFor(() => {
      expect(screen.getByText('¥150.25')).toBeInTheDocument();
    });
  });

  it('应该显示涨跌额和涨跌幅', async () => {
    render(<RealtimeQuote symbol="AAPL" />);

    await waitFor(() => {
      expect(screen.getByText('+2.50')).toBeInTheDocument();
      expect(screen.getByText('+1.69%')).toBeInTheDocument();
    });
  });

  it('应该显示详细信息', async () => {
    render(<RealtimeQuote symbol="AAPL" showDetails={true} />);

    await waitFor(() => {
      expect(screen.getByText('开盘价')).toBeInTheDocument();
      expect(screen.getByText('收盘价')).toBeInTheDocument();
      expect(screen.getByText('最高价')).toBeInTheDocument();
      expect(screen.getByText('最低价')).toBeInTheDocument();
      expect(screen.getByText('成交量')).toBeInTheDocument();
      expect(screen.getByText('成交额')).toBeInTheDocument();
    });
  });

  it('应该隐藏详细信息', async () => {
    render(<RealtimeQuote symbol="AAPL" showDetails={false} />);

    await waitFor(() => {
      expect(screen.queryByText('开盘价')).not.toBeInTheDocument();
    });
  });

  it('应该显示刷新按钮', async () => {
    render(<RealtimeQuote symbol="AAPL" showRefreshButton={true} />);

    await waitFor(() => {
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('应该隐藏刷新按钮', async () => {
    render(<RealtimeQuote symbol="AAPL" showRefreshButton={false} />);

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });

    // 应该没有刷新按钮
    const buttons = screen.queryAllByRole('button');
    expect(buttons.length).toBe(0);
  });

  it('应该显示加载状态', () => {
    mockedUseMarketStore.mockReturnValue({
      quotes: {},
      loadingQuotes: { AAPL: true },
      errors: {},
      fetchRealtimeQuote: mockFetchRealtimeQuote,
    });

    render(<RealtimeQuote symbol="AAPL" />);

    expect(screen.getByText('加载AAPL行情中...')).toBeInTheDocument();
  });

  it('应该显示错误状态', () => {
    mockedUseMarketStore.mockReturnValue({
      quotes: {},
      loadingQuotes: {},
      errors: { AAPL: new Error('加载失败') },
      fetchRealtimeQuote: mockFetchRealtimeQuote,
    });

    render(<RealtimeQuote symbol="AAPL" />);

    expect(screen.getAllByText('加载失败').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument();
  });

  it('应该显示无数据状态', () => {
    mockedUseMarketStore.mockReturnValue({
      quotes: {},
      loadingQuotes: {},
      errors: {},
      fetchRealtimeQuote: mockFetchRealtimeQuote,
    });

    render(<RealtimeQuote symbol="AAPL" />);

    expect(screen.getByText('暂无数据')).toBeInTheDocument();
  });

  it('应该处理点击事件', async () => {
    const onClick = vi.fn();
    render(<RealtimeQuote symbol="AAPL" onClick={onClick} />);

    await waitFor(() => {
      const card = screen.getByText('AAPL').closest('.ant-card');
      expect(card).toBeInTheDocument();
      if (card) {
        fireEvent.click(card);
        expect(onClick).toHaveBeenCalled();
      }
    });
  });

  it('应该使用正确的颜色显示涨跌', async () => {
    const { container } = render(<RealtimeQuote symbol="AAPL" />);

    await waitFor(() => {
      const priceTags = container.querySelectorAll('.ant-tag-red');
      expect(priceTags.length).toBeGreaterThan(0);
    });
  });

  it('应该显示下跌股票的正确颜色', async () => {
    const downQuote: MarketQuote = {
      ...mockQuote,
      change: -2.5,
      changePercent: -1.64,
    };

    mockedUseMarketStore.mockReturnValue({
      quotes: { AAPL: downQuote },
      loadingQuotes: {},
      errors: {},
      fetchRealtimeQuote: mockFetchRealtimeQuote,
    });

    const { container } = render(<RealtimeQuote symbol="AAPL" />);

    await waitFor(() => {
      const greenTags = container.querySelectorAll('.ant-tag-green');
      expect(greenTags.length).toBeGreaterThan(0);
    });
  });

  it('应该格式化成交量', async () => {
    render(<RealtimeQuote symbol="AAPL" showDetails={true} />);

    await waitFor(() => {
      expect(screen.getByText('5000.00万')).toBeInTheDocument();
      expect(screen.getByText('75.00亿')).toBeInTheDocument();
    });
  });

  it('应该显示更新时间', async () => {
    render(<RealtimeQuote symbol="AAPL" />);

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      // 时间格式的图标应该存在
      const timeIcon = document.querySelector('.anticon-clock-circle');
      expect(timeIcon).toBeInTheDocument();
    });
  });

  it('应该支持自定义样式', async () => {
    const customStyle = { backgroundColor: 'red', width: '500px' };
    const { container } = render(<RealtimeQuote symbol="AAPL" style={customStyle} />);

    await waitFor(() => {
      const card = container.querySelector('.ant-card');
      expect(card).toHaveStyle('width: 500px');
      expect(card?.getAttribute('style')).toContain('background-color: red');
    });
  });

  it('应该阻止点击事件冒泡（刷新按钮）', async () => {
    const onClick = vi.fn();
    const mockRefresh = vi.fn();

    mockedUseDataRefresh.mockReturnValue({
      refreshing: false,
      lastRefreshTime: Date.now(),
      refresh: mockRefresh,
      error: null,
    });

    render(<RealtimeQuote symbol="AAPL" onClick={onClick} showRefreshButton={true} />);

    await waitFor(() => {
      const reloadIcon = document.querySelector('.anticon-reload');
      const refreshBtn = reloadIcon?.closest('button');
      expect(refreshBtn).toBeTruthy();
      fireEvent.click(refreshBtn as Element);
      expect(mockRefresh).toHaveBeenCalled();
      expect(onClick).not.toHaveBeenCalled();
    });
  });
});
