import { describe, it, expect } from 'vitest';
import { calculatePositionsWinRate } from '../portfolioUtils';
import { AccountInfo } from '../../services/realTradingService';

describe('portfolioUtils - calculatePositionsWinRate', () => {
    it('should return 0 when accountInfo is null', () => {
        const result = calculatePositionsWinRate(null);
        expect(result.winRate).toBe(0);
        expect(result.total).toBe(0);
    });

    it('should calculate win rate correctly for array of positions', () => {
        const mockAccount: Partial<AccountInfo> = {
            positions: [
                { symbol: '600519', volume: 100, price: 1800, cost_price: 1700 }, // Win
                { symbol: '300750', volume: 200, price: 400, cost_price: 450 },   // Loss
                { symbol: '000001', volume: 0, price: 10, cost_price: 8 },      // Zero volume ignored
                { symbol: '600036', volume: 100, price: 35, cost_price: 30 }    // Win
            ] as any
        };

        const result = calculatePositionsWinRate(mockAccount as AccountInfo);
        expect(result.total).toBe(3); // 600519, 300750, 600036
        expect(result.winning).toBe(2); // 600519, 600036
        expect(result.winRate).toBeCloseTo(66.666, 1);
    });

    it('should calculate win rate correctly for object of positions', () => {
        const mockAccount: Partial<AccountInfo> = {
            positions: {
                '600519': { volume: 100, price: 1800, cost_price: 1700 }, // Win
                '300750': { volume: 200, price: 400, cost_price: 450 }   // Loss
            } as any
        };

        const result = calculatePositionsWinRate(mockAccount as AccountInfo);
        expect(result.total).toBe(2);
        expect(result.winning).toBe(1);
        expect(result.winRate).toBe(50);
    });

    it('should handle missing cost or price safely', () => {
        const mockAccount: Partial<AccountInfo> = {
            positions: [
                { symbol: '600519', volume: 100, price: 1800 }, // No cost, not a win
                { symbol: '300750', volume: 200, cost_price: 450 } // No price, not a win
            ] as any
        };

        const result = calculatePositionsWinRate(mockAccount as AccountInfo);
        expect(result.winning).toBe(0);
        expect(result.winRate).toBe(0);
    });
});
