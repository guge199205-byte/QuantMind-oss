import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getChartOption } from '../chartOptions';

describe('chartOptions tradeCount', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-21T12:00:00+08:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should render only the recent 7 days with integer y-axis steps', () => {
    const points = Array.from({ length: 10 }, (_, index) => ({
      timestamp: new Date(`2026-03-${String(index + 12).padStart(2, '0')}T00:00:00+08:00`).toISOString(),
      value: index + 1,
    }));

    const option = getChartOption('tradeCount', points) as any;

    expect(option.title.text).toBe('近7日交易次数');
    expect(option.xAxis.data).toHaveLength(7);
    expect(option.series[0].data).toEqual([4, 5, 6, 7, 8, 9, 10]);
    expect(option.yAxis.min).toBe(0);
    expect(option.yAxis.interval).toBe(2);
    expect(option.yAxis.max).toBe(10);
  });
});
