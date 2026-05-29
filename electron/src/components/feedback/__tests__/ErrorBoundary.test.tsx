import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary, withErrorBoundary } from '../ErrorBoundary';

// 会抛出错误的组件
const ThrowError: React.FC<{ shouldThrow?: boolean }> = ({ shouldThrow = true }) => {
  if (shouldThrow) {
    throw new Error('Test error');
  }
  return <div>No error</div>;
};

describe('ErrorBoundary', () => {
  // 抑制控制台错误输出
  const originalError = console.error;
  beforeAll(() => {
    console.error = vi.fn();
  });

  afterAll(() => {
    console.error = originalError;
  });

  it('应该捕获子组件错误并显示错误UI', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('抱歉，出现了一些问题')).toBeTruthy();
  });

  it('正常情况下应该渲染子组件', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('No error')).toBeTruthy();
  });

  it('应该显示自定义fallback', () => {
    const customFallback = <div data-testid="custom-fallback">Custom Error</div>;

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByTestId('custom-fallback')).toBeTruthy();
  });

  it('应该调用onError回调', () => {
    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalled();
  });

  it('showDetails为true时应该显示错误详情', () => {
    render(
      <ErrorBoundary showDetails={true}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('错误详情:')).toBeTruthy();
  });

  it('应该有重试按钮', () => {
    const { container } = render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    // 文本可能有空格分隔
    const text = container.textContent || '';
    expect(text.replace(/\s/g, '')).toContain('重试');
  });

  it('应该有刷新页面按钮', () => {
    const { container } = render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(container.textContent).toContain('刷新页面');
  });
});

describe('withErrorBoundary', () => {
  const originalError = console.error;
  beforeAll(() => {
    console.error = vi.fn();
  });

  afterAll(() => {
    console.error = originalError;
  });

  it('应该包装组件并捕获错误', () => {
    const WrappedComponent = withErrorBoundary(ThrowError);

    render(<WrappedComponent />);

    expect(screen.getByText('抱歉，出现了一些问题')).toBeTruthy();
  });

  it('正常情况下应该渲染原组件', () => {
    const WrappedComponent = withErrorBoundary(ThrowError);

    render(<WrappedComponent shouldThrow={false} />);

    expect(screen.getByText('No error')).toBeTruthy();
  });

  it('应该设置正确的displayName', () => {
    const TestComponent: React.FC = () => <div>Test</div>;
    TestComponent.displayName = 'TestComponent';

    const WrappedComponent = withErrorBoundary(TestComponent);

    expect(WrappedComponent.displayName).toBe('withErrorBoundary(TestComponent)');
  });
});
