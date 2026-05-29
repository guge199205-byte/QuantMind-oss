import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import {
  useDebounce,
  useDebouncedCallback,
  useThrottle,
  useThrottledCallback
} from '../useDebounce';

describe('useDebounce', () => {
  it('应该返回初始值', () => {
    const { result } = renderHook(() => useDebounce('initial', 300));
    expect(result.current).toBe('initial');
  });

  it('应该在真实定时器下工作', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 100),
      { initialProps: { value: 'initial' } }
    );

    expect(result.current).toBe('initial');
    rerender({ value: 'updated' });

    // 等待防抖时间
    await new Promise(resolve => setTimeout(resolve, 150));
    expect(result.current).toBe('updated');
  });

  it('应该使用自定义延迟时间', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 200),
      { initialProps: { value: 'initial' } }
    );

    rerender({ value: 'updated' });
    await new Promise(resolve => setTimeout(resolve, 100));
    expect(result.current).toBe('initial');

    await new Promise(resolve => setTimeout(resolve, 150));
    expect(result.current).toBe('updated');
  });
});

describe('useDebouncedCallback', () => {
  it('应该延迟执行回调', async () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 100));

    result.current('arg1', 'arg2');
    expect(callback).not.toHaveBeenCalled();

    await new Promise(resolve => setTimeout(resolve, 150));
    expect(callback).toHaveBeenCalledWith('arg1', 'arg2');
  });

  it('应该取消之前的调用', async () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 100));

    result.current('call1');
    await new Promise(resolve => setTimeout(resolve, 50));
    result.current('call2');
    await new Promise(resolve => setTimeout(resolve, 150));

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith('call2');
  });
});

describe('useThrottle', () => {
  it('应该返回初始值', () => {
    const { result } = renderHook(() => useThrottle('initial', 300));
    expect(result.current).toBe('initial');
  });

  it('应该节流更新值', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useThrottle(value, 100),
      { initialProps: { value: 'initial' } }
    );

    expect(result.current).toBe('initial');
    rerender({ value: 'update1' });

    // 等待节流时间后，值应该更新
    await new Promise(resolve => setTimeout(resolve, 150));
    expect(result.current).toBe('update1');
  });
});

describe('useThrottledCallback', () => {
  it('应该立即执行第一次调用', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottledCallback(callback, 300));

    result.current('call1');
    expect(callback).toHaveBeenCalledWith('call1');
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('应该节流后续调用', async () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottledCallback(callback, 100));

    result.current('call1');
    expect(callback).toHaveBeenCalledTimes(1);

    result.current('call2');
    expect(callback).toHaveBeenCalledTimes(1);

    await new Promise(resolve => setTimeout(resolve, 150));
    result.current('call3');
    expect(callback).toHaveBeenCalledTimes(2);
  });
});
