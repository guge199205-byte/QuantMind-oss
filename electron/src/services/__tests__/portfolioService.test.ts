/**
 * PortfolioService 单元测试
 *
 * @author QuantMind Team
 * @date 2025-02-13
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// 使用 vi.hoisted 确保 mocks 变量被提升，可以在 vi.mock 工厂函数中访问
const mocks = vi.hoisted(() => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    request: vi.fn(),
}));

vi.mock('axios', () => {
    return {
        default: {
            create: () => ({
                get: mocks.get,
                post: mocks.post,
                put: mocks.put,
                delete: mocks.delete,
                patch: mocks.patch,
                request: mocks.request,
                interceptors: {
                    request: { use: vi.fn() },
                    response: { use: vi.fn() },
                },
            }),
            get: mocks.get,
            post: mocks.post,
            put: mocks.put,
            isAxiosError: () => false,
        },
        // 支持 Named import
        create: () => ({
            get: mocks.get,
            post: mocks.post,
            put: mocks.put,
            delete: mocks.delete,
            patch: mocks.patch,
            request: mocks.request,
            interceptors: {
                request: { use: vi.fn() },
                response: { use: vi.fn() },
            },
        }),
        isAxiosError: () => false,
        __esModule: true,
    };
});

import { portfolioService } from '../portfolioService';

const mockBindingStatus = (overrides?: Record<string, unknown>) => ({
    data: {
        online: false,
        user_id: 'test_user',
        tenant_id: 'default',
        account_id: '8886664999',
        account_reported_at: '2026-04-11T10:00:00+00:00',
        ...overrides,
    },
});

describe('PortfolioService', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.stubGlobal('localStorage', {
            getItem: vi.fn(() => null),
            setItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn(),
        });
    });

    describe('getDefaultFundData', () => {
        it('应该返回初始资金100万的默认数据', () => {
            const data = portfolioService.getDefaultFundData();

            expect(data.totalAsset).toBe(1_000_000);
            expect(data.availableBalance).toBe(1_000_000);
            expect(data.frozenBalance).toBe(0);
            expect(data.todayPnL).toBe(0);
            expect(data.dailyReturn).toBe(0);
            expect(data.totalPnL).toBe(0);
            expect(data.totalReturn).toBe(0);
            expect(data.initialCapital).toBe(1_000_000);
            expect(data.winRate).toBe(0);
            expect(data.maxDrawdown).toBe(0);
            expect(data.sharpeRatio).toBe(0);
            expect(data.lastUpdate).toBeDefined();
        });
    });

    describe('getFundOverview', () => {
        it('后端不可用时应该降级到默认数据并标记 isSimulated', async () => {
            mocks.get.mockRejectedValue(new Error('Network Error'));

            const result = await portfolioService.getFundOverview('test_user');

            expect(result.isSimulated).toBe(true);
            expect(result.data.totalAsset).toBe(1_000_000);
            expect(result.data.initialCapital).toBe(1_000_000);
        });

        it('实盘模式下应优先读取 real 账户并正确映射 available_cash', async () => {
            const mockAccount = {
                tenant_id: 'default',
                user_id: 'test_user',
                total_asset: 1_050_000,
                available_cash: 800_000,
                frozen_balance: 250_000,
                total_pnl: 50_000,
                daily_pnl: 5_000,
                daily_return_pct: 0.5,
                baseline: {
                    initial_equity: 1_000_000,
                    day_open_equity: 1_000_000,
                    month_open_equity: 1_010_000,
                },
                positions: [],
            };

            mocks.get
                .mockResolvedValueOnce(mockBindingStatus())
                .mockResolvedValueOnce({ data: mockAccount });

            const result = await portfolioService.getFundOverview('test_user', 'real');

            expect(result.isSimulated).toBe(false);
            expect(result.data.totalAsset).toBe(1_050_000);
            expect(result.data.availableBalance).toBe(800_000);
            expect(result.data.frozenBalance).toBe(250_000);
            expect(result.data.totalPnL).toBe(50_000);
            expect(result.data.todayPnL).toBe(5_000);
            expect(result.data.dailyReturn).toBe(0.5);
            expect(result.data.initialCapital).toBe(1_000_000);
        });

        it('cash=0 时不应回退到 totalAsset', async () => {
            const mockAccount = {
                tenant_id: 'default',
                user_id: 'test_user',
                total_asset: 1_050_000,
                cash: 0,
                total_pnl: 50_000,
                positions: [],
            };

            mocks.get
                .mockResolvedValueOnce(mockBindingStatus())
                .mockResolvedValueOnce({ data: mockAccount });

            const result = await portfolioService.getFundOverview('test_user', 'real');

            expect(result.isSimulated).toBe(false);
            expect(result.data.availableBalance).toBe(0);
        });

        it('实盘未上报时应保留实盘口径并显示 0', async () => {
            mocks.get.mockResolvedValueOnce(mockBindingStatus({
                account_reported_at: null,
            }));

            const result = await portfolioService.getFundOverview('test_user', 'real');

            expect(result.isSimulated).toBe(false);
            expect(result.data.totalAsset).toBe(0);
            expect(result.data.availableBalance).toBe(0);
            expect(result.data.accountOnline).toBe(false);
        });

        it('实盘未绑定时应直接返回空实盘口径并避免请求 /account', async () => {
            mocks.get.mockResolvedValueOnce(mockBindingStatus({
                account_id: null,
                account_reported_at: null,
            }));

            const result = await portfolioService.getFundOverview('test_user', 'real');

            expect(result.isSimulated).toBe(false);
            expect(result.data.totalAsset).toBe(0);
            expect(result.data.availableBalance).toBe(0);
            expect(result.data.accountOnline).toBe(false);
        });

        it('模拟盘应优先使用 simulation settings 里的初始资金计算收益率', async () => {
            const mockSimulationAccount = {
                total_asset: 2_100_000,
                cash: 1_400_000,
                total_pnl: 100_000,
                today_pnl: 1_000,
                positions: {},
            };
            const mockSettings = {
                initial_cash: 2_000_000,
                can_modify: true,
                cooldown_days: 30,
                amount_step: 100_000,
            };

            mocks.get
                .mockResolvedValueOnce({ data: { success: true, data: mockSimulationAccount } })
                .mockResolvedValueOnce({ data: { success: true, data: mockSettings } });

            const result = await portfolioService.getFundOverview('test_user', 'simulation');

            expect(result.isSimulated).toBe(true);
            expect(result.data.initialCapital).toBe(2_000_000);
            expect(result.data.totalReturn).toBe(5);
        });

        it('实盘旧收益率字段为 0 但总盈亏可推导时，应回退到基线推导收益率', async () => {
            const mockAccount = {
                tenant_id: 'default',
                user_id: 'test_user',
                total_asset: 21_644_376.54,
                cash: 5_000_000,
                total_pnl: 644_376.54,
                total_return: 0,
                daily_pnl: 0,
                daily_return: 0,
                baseline: {
                    initial_equity: 21_000_000,
                    day_open_equity: 21_644_376.54,
                    month_open_equity: 21_644_376.54,
                },
                positions: [],
            };

            mocks.get
                .mockResolvedValueOnce(mockBindingStatus())
                .mockResolvedValueOnce({ data: mockAccount });

            const result = await portfolioService.getFundOverview('test_user', 'real');

            expect(result.isSimulated).toBe(false);
            expect(result.data.totalPnL).toBeCloseTo(644_376.54);
            expect(result.data.totalReturn).toBeCloseTo((644_376.54 / 21_000_000) * 100, 2);
            expect(result.data.dailyReturn).toBe(0);
        });

        it('实盘显式收益率与盈亏基线冲突时，应优先使用同口径推导值', async () => {
            const mockAccount = {
                tenant_id: 'default',
                user_id: 'test_user',
                total_asset: 21_652_375.54,
                cash: 5_000_000,
                total_pnl: 644_376.54,
                total_return_ratio: 0.0004,
                daily_pnl: 7_999,
                daily_return_ratio: 0.0004,
                baseline: {
                    initial_equity: 21_000_000,
                    day_open_equity: 21_644_376.54,
                    month_open_equity: 21_644_376.54,
                },
                positions: [],
            };

            mocks.get
                .mockResolvedValueOnce(mockBindingStatus())
                .mockResolvedValueOnce({ data: mockAccount });

            const result = await portfolioService.getFundOverview('test_user', 'real');

            expect(result.isSimulated).toBe(false);
            expect(result.data.initialCapital).toBeCloseTo(21_007_999);
            expect(result.data.totalPnL).toBeCloseTo(644_376.54);
            expect(result.data.totalReturn).toBeCloseTo((644_376.54 / 21_007_999) * 100, 2);
            expect(result.data.dailyReturn).toBeCloseTo((7_999 / 21_644_376.54) * 100, 2);
        });

        it('实盘资金概览应按当前权益减去总盈亏计算初始权益', async () => {
            const mockAccount = {
                tenant_id: 'default',
                user_id: 'test_user',
                total_asset: 21_652_375.54,
                cash: 5_000_000,
                total_pnl: 644_376.54,
                baseline: {
                    initial_equity: 21_644_376.54,
                },
                positions: [],
            };

            mocks.get
                .mockResolvedValueOnce(mockBindingStatus())
                .mockResolvedValueOnce({ data: mockAccount });

            const result = await portfolioService.getFundOverview('test_user', 'real');

            expect(result.isSimulated).toBe(false);
            expect(result.data.initialCapital).toBeCloseTo(21_007_999);
        });
    });
});
