import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDataRefresh } from '../useDataRefresh';

describe('useDataRefresh', () => {
  it('应该初始化默认值', () => {
    const { result } = renderHook(() => useDataRefresh({ immediate: false, enabled: false }));

    expect(result.current.refreshing).toBe(false);
    expect(result.current.lastRefreshTime).toBeNull();
    expect(result.current.error).toBeNull();
    expect(typeof result.current.refresh).toBe('function');
  });

  it('应该不立即执行刷新（immediate=false）', () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);

    renderHook(() =>
      useDataRefresh({
        onRefresh,
        immediate: false,
        enabled: false,
      })
    );

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it('应该手动刷新', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useDataRefresh({
        onRefresh,
        immediate: false,
        enabled: false,
      })
    );

    expect(onRefresh).not.toHaveBeenCalled();

    // 手动刷新
    await act(async () => {
      await result.current.refresh();
    });

    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(result.current.lastRefreshTime).not.toBeNull();
  });

  it('应该禁用自动刷新', () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);

    renderHook(() =>
      useDataRefresh({
        onRefresh,
        interval: 1000,
        enabled: false,
        immediate: false,
      })
    );

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it('应该处理刷新错误', async () => {
    const error = new Error('刷新失败');
    const onRefresh = vi.fn().mockRejectedValue(error);
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useDataRefresh({
        onRefresh,
        onError,
        immediate: false,
        enabled: false,
      })
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.error).toEqual(error);
    expect(onError).toHaveBeenCalledWith(error);
  });

  it('应该更新最后刷新时间', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useDataRefresh({
        onRefresh,
        immediate: false,
        enabled: false,
      })
    );

    expect(result.current.lastRefreshTime).toBeNull();

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.lastRefreshTime).not.toBeNull();
    expect(typeof result.current.lastRefreshTime).toBe('number');
  });

  it('应该在组件卸载时清理', () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);

    const { unmount } = renderHook(() =>
      useDataRefresh({
        onRefresh,
        interval: 1000,
        enabled: true,
        immediate: false,
      })
    );

    unmount();

    // 卸载后应该清理，不再调用刷新
    expect(onRefresh).not.toHaveBeenCalled();
  });
});
