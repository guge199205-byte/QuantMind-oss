// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useIntelligenceCharts } from '../useIntelligenceCharts';
import { portfolioService } from '../../services/portfolioService';
import { tradingService } from '../../services/tradingService';
import { realTradingService } from '../../services/realTradingService';
import { modelTrainingService } from '../../services/modelTrainingService';
import { useWebSocket } from '../../contexts/WebSocketContext';
import { authService } from '../../features/auth/services/authService';

// Mock services
vi.mock('../../services/portfolioService', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual as any,
        portfolioService: {
            getDailyReturns: vi.fn(),
            getPositionDistribution: vi.fn()
        }
    };
});
vi.mock('../../services/tradingService', () => ({
    tradingService: {
        getTradeStats: vi.fn()
    }
}));
vi.mock('../../services/realTradingService', () => ({
    realTradingService: {
        getAccount: vi.fn(),
        getAccountLedgerDaily: vi.fn(),
    }
}));
vi.mock('../../services/modelTrainingService', () => ({
    modelTrainingService: {
        resolveInferenceDateByCalendar: vi.fn(),
        prevTradingDay: vi.fn(),
    }
}));
vi.mock('../../features/auth/services/authService', () => ({
    authService: {
        getStoredUser: vi.fn(() => null),
    }
}));

// Mock WebSocket context
const mockOnMessage = vi.fn();
vi.mock('../../contexts/WebSocketContext', () => ({
    useWebSocket: () => ({
        onMessage: mockOnMessage
    })
}));

describe('useIntelligenceCharts', () => {
    const mockDailyReturns = [{ timestamp: '2023-01-01', value: 100 }];
    const mockTradeStats = [{ timestamp: '2023-01-01', value: 5 }];
    const mockPositionDistribution = [{ name: 'Stock A', value: 50, code: 'A', ratio: 50 }];
    const mockLedgerDaily = [{ snapshot_date: '2023-01-01', snapshot_kind: 'daily_ledger', today_pnl_raw: 120, daily_return_pct: 1.2 }];

    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(authService.getStoredUser).mockReturnValue(null as any);
        vi.mocked(modelTrainingService.resolveInferenceDateByCalendar).mockResolvedValue({ date: '2023-01-03', adjusted: false } as any);
        vi.mocked(modelTrainingService.prevTradingDay)
            .mockImplementation(async (_market: string, date: string) => {
                const cursor = new Date(`${date}T00:00:00Z`);
                do {
                    cursor.setUTCDate(cursor.getUTCDate() - 1);
                } while (cursor.getUTCDay() === 0 || cursor.getUTCDay() === 6);
                return cursor.toISOString().slice(0, 10);
            });
        // Setup default mock implementation for onMessage to return unsubscribe function
        mockOnMessage.mockReturnValue(() => { });
    });

    it('should fetch all chart data successfully', async () => {
        vi.mocked(portfolioService.getDailyReturns).mockResolvedValue(mockDailyReturns);
        vi.mocked(tradingService.getTradeStats).mockResolvedValue(mockTradeStats);
        vi.mocked(portfolioService.getPositionDistribution).mockResolvedValue(mockPositionDistribution);
        vi.mocked(realTradingService.getAccount).mockResolvedValue(null as any);
        vi.mocked(realTradingService.getAccountLedgerDaily).mockResolvedValue(mockLedgerDaily as any);

        const { result } = renderHook(() => useIntelligenceCharts());

        expect(result.current.loading).toBe(true);

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.data.dailyReturn).toHaveLength(30);
        expect(result.current.data.dailyReturn.at(-1)).toEqual({
            timestamp: '2023-01-03T00:00:00Z',
            value: 0,
            label: '今日实时',
        });
        expect(result.current.data.tradeCount).toHaveLength(7);
        expect(result.current.data.tradeCount.at(-1)).toEqual({
            timestamp: '2023-01-03T00:00:00Z',
            value: 0,
            label: undefined,
        });
        expect(vi.mocked(tradingService.getTradeStats)).toHaveBeenCalledWith('current', '1w');
        expect(result.current.data.positionRatio).toEqual([
            { name: '持仓市值', code: 'HOLDING', value: 50, ratio: 1 },
            { name: '可用资金', code: 'CASH', value: 0, ratio: 0 },
        ]);
        expect(result.current.error).toBeNull();
        expect(result.current.data.dailyReturn.some((item) => item.timestamp === '2023-01-01T00:00:00Z')).toBe(false);
        expect(result.current.data.dailyReturn.some((item) => item.timestamp === '2023-01-02T00:00:00Z')).toBe(true);
    });

    it('should handle API errors', async () => {
        vi.mocked(portfolioService.getDailyReturns).mockRejectedValue(new Error('Network Error'));
        // Even if one fails, Promise.all fails. Hook catches error.
        vi.mocked(realTradingService.getAccount).mockResolvedValue(null as any);
        vi.mocked(realTradingService.getAccountLedgerDaily).mockResolvedValue([] as any);

        const { result } = renderHook(() => useIntelligenceCharts());

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.error).toBe('Network Error');
    });

    it('should resolve current user id from stored user', async () => {
        vi.mocked(authService.getStoredUser).mockReturnValue({ user_id: 'user-001' } as any);
        vi.mocked(portfolioService.getDailyReturns).mockResolvedValue(mockDailyReturns);
        vi.mocked(tradingService.getTradeStats).mockResolvedValue(mockTradeStats);
        vi.mocked(portfolioService.getPositionDistribution).mockResolvedValue(mockPositionDistribution);
        vi.mocked(realTradingService.getAccount).mockResolvedValue(null as any);
        vi.mocked(realTradingService.getAccountLedgerDaily).mockResolvedValue([] as any);

        const { result } = renderHook(() => useIntelligenceCharts('current'));

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(vi.mocked(tradingService.getTradeStats)).toHaveBeenCalledWith('user-001', '1w');
    });

    it('should handle WebSocket chart updates for dailyReturn', async () => {
        vi.mocked(portfolioService.getDailyReturns).mockResolvedValue(mockDailyReturns);
        vi.mocked(tradingService.getTradeStats).mockResolvedValue(mockTradeStats);
        vi.mocked(portfolioService.getPositionDistribution).mockResolvedValue(mockPositionDistribution);
        vi.mocked(realTradingService.getAccount).mockResolvedValue(null as any);
        vi.mocked(realTradingService.getAccountLedgerDaily).mockResolvedValue([] as any);

        let messageCallback: (type: string, payload: any) => void;
        mockOnMessage.mockImplementation((cb) => {
            messageCallback = cb;
            return () => { };
        });

        const { result } = renderHook(() => useIntelligenceCharts());

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        // Simulate WebSocket message
        act(() => {
            if (messageCallback) {
                messageCallback('chart_update', {
                    chartType: 'dailyReturn',
                    value: 200
                });
            }
        });

        const dailyReturns = result.current.data.dailyReturn;
        expect(dailyReturns.length).toBe(30);
        expect(dailyReturns[dailyReturns.length - 1].value).toBe(200);
        expect(dailyReturns[dailyReturns.length - 1].label).toBe('实时数据');
    });

    it('should parse nested position distribution payload (data.data.sectors)', async () => {
        vi.mocked(portfolioService.getDailyReturns).mockResolvedValue(mockDailyReturns);
        vi.mocked(tradingService.getTradeStats).mockResolvedValue(mockTradeStats);
        vi.mocked(portfolioService.getPositionDistribution).mockResolvedValue({
            data: {
                data: {
                    sectors: {
                        Tech: 0.62,
                        Finance: 0.38,
                    },
                },
            },
        } as any);
        vi.mocked(realTradingService.getAccount).mockResolvedValue(null as any);
        vi.mocked(realTradingService.getAccountLedgerDaily).mockResolvedValue([] as any);

        const { result } = renderHook(() => useIntelligenceCharts());

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.hasPositionRatio).toBe(true);
        expect(result.current.data.positionRatio).toEqual([
            { name: '持仓市值', code: 'HOLDING', value: 1, ratio: 1 },
            { name: '可用资金', code: 'CASH', value: 0, ratio: 0 },
        ]);
    });

    it('should fallback to assets map when sectors is empty', async () => {
        vi.mocked(portfolioService.getDailyReturns).mockResolvedValue(mockDailyReturns);
        vi.mocked(tradingService.getTradeStats).mockResolvedValue(mockTradeStats);
        vi.mocked(portfolioService.getPositionDistribution).mockResolvedValue({
            data: {
                sectors: {},
                assets: {
                    Stock: 0.87,
                    Cash: 0.13,
                },
            },
        } as any);
        vi.mocked(realTradingService.getAccount).mockResolvedValue(null as any);
        vi.mocked(realTradingService.getAccountLedgerDaily).mockResolvedValue([] as any);

        const { result } = renderHook(() => useIntelligenceCharts());

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.hasPositionRatio).toBe(true);
        expect(result.current.data.positionRatio).toEqual([
            { name: '持仓市值', code: 'HOLDING', value: 0.87, ratio: 0.87 },
            { name: '可用资金', code: 'CASH', value: 0.13, ratio: 0.13 },
        ]);
    });
});
