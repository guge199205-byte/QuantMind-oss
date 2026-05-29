import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo
    });

    // 记录错误到控制台
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError) {
      // 如果提供了自定义fallback，使用它
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // 默认错误UI
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
            <div className="text-center">
              <div className="text-6xl mb-4">⚠️</div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">出现错误</h2>
              <p className="text-gray-600 mb-6">应用遇到了一个意外错误，请尝试刷新页面。</p>

              <div className="space-y-3">
                <button
                  onClick={this.handleReset}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                >
                  重试
                </button>

                <button
                  onClick={() => window.location.reload()}
                  className="w-full px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  刷新页面
                </button>
              </div>

              {/* 开发模式下显示错误详情 */}
              {import.meta.env.DEV && this.state.error && (
                <details className="mt-6 text-left">
                  <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700">
                    错误详情（开发模式）
                  </summary>
                  <div className="mt-2 p-3 bg-gray-100 rounded text-xs text-gray-700 overflow-auto">
                    <pre>{this.state.error.toString()}</pre>
                    {this.state.errorInfo && (
                      <pre className="mt-2">{this.state.errorInfo.componentStack}</pre>
                    )}
                  </div>
                </details>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// 轻量级错误边界（用于包装单个组件）
interface SimpleErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

export const SimpleErrorBoundary: React.FC<SimpleErrorBoundaryProps> = ({
  children,
  fallback,
  onError
}) => {
  return (
    <ErrorBoundary
      fallback={fallback || (
        <div className="p-4 text-center">
          <div className="text-red-500 text-sm">组件加载失败</div>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 text-xs text-blue-600 hover:text-blue-800"
          >
            刷新重试
          </button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
};
