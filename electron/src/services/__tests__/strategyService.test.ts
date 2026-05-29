import { describe, it, expect, vi, beforeEach } from 'vitest';
import { strategyService } from '../strategyService';
import { apiClient } from '../api-client';
import { API_ENDPOINTS } from '../config';

vi.mock('../api-client', () => ({
    apiClient: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

describe('strategyService', () => {
    const mockStrategies = [
        {
            id: '1',
            name: 'Test Strategy',
            status: 'running',
            total_return: 10,
            today_return: 1,
            risk_level: 'medium',
            created_at: '2025-01-01T00:00:00Z',
            updated_at: '2025-01-01T00:00:00Z',
        },
    ];

    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('getStrategies', () => {
        it('should fetch strategies successfully', async () => {
            vi.mocked(apiClient.get).mockResolvedValue({
                code: 200,
                message: 'Success',
                data: mockStrategies,
            });

            const response = await strategyService.getStrategies();

            expect(response.code).toBe(200);
            expect(response.data).toHaveLength(1);
            expect(response.data[0]).toMatchObject(mockStrategies[0]);
            expect(apiClient.get).toHaveBeenCalledWith(API_ENDPOINTS.STRATEGIES);
        });

        it('should throw on request failure', async () => {
            vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'));

            await expect(strategyService.getStrategies()).rejects.toThrow('Network error');
        });

        it('should normalize mixed backend strategy fields', async () => {
            vi.mocked(apiClient.get).mockResolvedValue({
                code: 200,
                message: 'Success',
                data: {
                    items: [
                        {
                            strategy_id: 101,
                            strategy_name: 'Alpha',
                            status: 'active',
                            total_return: '12.3',
                            today_return: '0.4',
                            risk_level: 'HIGH',
                            error_code: 'EXEC_TIMEOUT',
                            error_message: 'executor timed out',
                            last_failed_at: '2026-02-13T10:00:00Z',
                        },
                    ],
                },
            });

            const response = await strategyService.getStrategies();

            expect(response.code).toBe(200);
            expect(response.data).toHaveLength(1);
            expect(response.data[0].id).toBe('101');
            expect(response.data[0].name).toBe('Alpha');
            expect(response.data[0].status).toBe('running');
            expect(response.data[0].risk_level).toBe('high');
            expect(response.data[0].error_code).toBe('EXEC_TIMEOUT');
            expect(response.data[0].error_message).toBe('executor timed out');
            expect(response.data[0].last_failed_at).toBe('2026-02-13T10:00:00Z');
        });

        it('should treat plain StrategyListResponse as success', async () => {
            vi.mocked(apiClient.get).mockResolvedValue({
                total: 1,
                strategies: [
                    {
                        id: '42',
                        name: 'Live Strategy',
                        effective_status: 'running',
                        total_return: 3.2,
                        today_return: 0.7,
                        updated_at: '2026-03-20T08:00:00Z',
                    },
                ],
            });

            const response = await strategyService.getStrategies();

            expect(response.code).toBe(200);
            expect(response.data).toHaveLength(1);
            expect(response.data[0].status).toBe('running');
            expect(response.data[0].id).toBe('42');
        });
    });

    describe('startStrategy', () => {
        it('should start strategy successfully', async () => {
            vi.mocked(apiClient.post).mockResolvedValue({
                code: 200,
                message: 'Success',
                data: { success: true, message: 'Started', status: 'running' },
            });

            const response = await strategyService.startStrategy('1');

            expect(response.code).toBe(200);
            expect(apiClient.post).toHaveBeenCalledWith(API_ENDPOINTS.STRATEGY_START('1'));
        });
    });

    describe('stopStrategy', () => {
        it('should stop strategy successfully', async () => {
            vi.mocked(apiClient.post).mockResolvedValue({
                code: 200,
                message: 'Success',
                data: { success: true, message: 'Stopped', status: 'paused' },
            });

            const response = await strategyService.stopStrategy('1');

            expect(response.code).toBe(200);
            expect(apiClient.post).toHaveBeenCalledWith(API_ENDPOINTS.STRATEGY_STOP('1'));
        });
    });
});
