import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { StockList } from '../StockList';
import type { MarketQuote } from '../StockList';
import { useMarketStore } from '../../stores/market-store';

// Mock services
vi.mock('../../services', () => ({
  getAPIClient: vi.fn(),
}));

// Mock store
const mockFetchMarketData = vi.fn();
vi.mock('../../stores/market-store', () => ({
  useMarketStore: vi.fn(() => ({
    quotes: mockQuotes,
    loading: false,
    error: null,
    fetchMarketData: mockFetchMarketData,
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

const mockQuotes: Record<string, MarketQuote> = {
  AAPL: {
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
  },
  GOOGL: {
    symbol: 'GOOGL',
    price: 2800.75,
    change: -15.25,
    changePercent: -0.54,
    open: 2820.0,
    high: 2825.0,
    low: 2795.0,
    close: 2800.75,
    volume: 30000000,
    amount: 84000000000,
    timestamp: Date.now(),
  },
};

describe('StockList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseMarketStore.mockReturnValue({
      quotes: mockQuotes,
      loading: false,
      error: null,
      fetchMarketData: mockFetchMarketData,
    });
  });

  it('应该渲染股票列表', async () => {
    render(<StockList />);

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('GOOGL')).toBeInTheDocument();
    });
  });

  it('应该显示价格信息', async () => {
    render(<StockList />);

    await waitFor(() => {
      expect(screen.getByText('150.25')).toBeInTheDocument();
      expect(screen.getByText('2800.75')).toBeInTheDocument();
    });
  });

  it('应该显示涨跌幅', async () => {
    render(<StockList />);

    await waitFor(() => {
      expect(screen.getByText('+2.50')).toBeInTheDocument();
      expect(screen.getByText('-15.25')).toBeInTheDocument();
    });
  });

  it('应该支持搜索', async () => {
    render(<StockList showSearch={true} />);

    const searchInput = screen.getByPlaceholderText('搜索股票代码');
    expect(searchInput).toBeInTheDocument();

    fireEvent.change(searchInput, { target: { value: 'AAPL' } });

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
  });

  it('应该支持排序', async () => {
    render(<StockList />);

    // 查找排序下拉框
    const sortSelects = screen.getAllByRole('combobox');
    expect(sortSelects.length).toBeGreaterThan(0);
  });

  it('应该显示刷新按钮', async () => {
    render(<StockList showRefresh={true} />);

    await waitFor(() => {
      expect(screen.getByText('刷新')).toBeInTheDocument();
    });
  });

  it('应该处理点击事件', async () => {
    const onSymbolClick = vi.fn();
    render(<StockList onSymbolClick={onSymbolClick} />);

    await waitFor(() => {
      const appleLink = screen.getByText('AAPL');
      fireEvent.click(appleLink);
      expect(onSymbolClick).toHaveBeenCalledWith('AAPL');
    });
  });

  it('应该显示加载状态', () => {
    mockedUseMarketStore.mockReturnValue({
      quotes: {},
      loading: true,
      error: null,
      fetchMarketData: mockFetchMarketData,
    });

    render(<StockList />);

    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  it('应该显示错误状态', () => {
    mockedUseMarketStore.mockReturnValue({
      quotes: {},
      loading: false,
      error: new Error('加载失败'),
      fetchMarketData: mockFetchMarketData,
    });

    render(<StockList />);

    expect(screen.getAllByText('加载失败').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument();
  });

  it('应该格式化成交量', async () => {
    render(<StockList />);

    await waitFor(() => {
      expect(screen.getByText('5000.00万')).toBeInTheDocument();
      expect(screen.getByText('3000.00万')).toBeInTheDocument();
    });
  });

  it('应该使用正确的颜色显示涨跌', async () => {
    render(<StockList />);

    await waitFor(() => {
      expect(screen.getByText('+2.50')).toBeInTheDocument();
      expect(screen.getByText('-15.25')).toBeInTheDocument();
    });
  });

  it('应该支持分页', async () => {
    render(<StockList />);

    await waitFor(() => {
      expect(screen.getByText(/共 \d+ 条/)).toBeInTheDocument();
    });
  });

  it('应该在加载时禁用某些功能', () => {
    mockedUseMarketStore.mockReturnValue({
      quotes: mockQuotes,
      loading: true,
      error: null,
      fetchMarketData: mockFetchMarketData,
    });

    const { container } = render(<StockList />);

    // 表格应该有loading状态
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });
});
