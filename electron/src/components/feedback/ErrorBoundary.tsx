import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Result, Button } from 'antd';
import { FrownOutlined } from '@ant-design/icons';

/**
 * 错误边界组件
 * 捕获组件树中的JavaScript错误，记录错误并显示备用UI
 */

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  showDetails?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // 记录错误到错误报告服务
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    this.setState({
      error,
      errorInfo
    });

    // 调用外部错误处理函数
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // 可以在这里将错误发送到日志服务
    this.logErrorToService(error, errorInfo);
  }

  logErrorToService(error: Error, errorInfo: ErrorInfo): void {
    // 实现错误日志服务
    // 例如：发送到Sentry、LogRocket等
    const errorLog = {
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString()
    };

    console.log('Error logged:', errorLog);

    // TODO: 发送到远程日志服务
    // logService.log(errorLog);
  }

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    const { hasError, error, errorInfo } = this.state;
    const { children, fallback, showDetails = false } = this.props;

    if (hasError) {
      // 如果提供了自定义fallback，使用它
      if (fallback) {
        return fallback;
      }

      // 默认错误UI
      return (
        <div style={{
          padding: '40px 20px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '400px'
        }}>
          <Result
            status="error"
            icon={<FrownOutlined />}
            title="抱歉，出现了一些问题"
            subTitle={error?.message || '页面加载失败，请稍后重试'}
            extra={[
              <Button type="primary" key="reset" onClick={this.handleReset}>
                重试
              </Button>,
              <Button key="reload" onClick={this.handleReload}>
                刷新页面
              </Button>
            ]}
          >
            {showDetails && error && (
              <div style={{
                marginTop: 16,
                textAlign: 'left',
                background: '#f5f5f5',
                padding: 16,
                borderRadius: 4,
                maxWidth: 600,
                overflow: 'auto'
              }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>错误详情:</div>
                <pre style={{
                  fontSize: 12,
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {error.stack}
                </pre>
                {errorInfo && (
                  <>
                    <div style={{ marginTop: 16, marginBottom: 8, fontWeight: 500 }}>
                      组件堆栈:
                    </div>
                    <pre style={{
                      fontSize: 12,
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word'
                    }}>
                      {errorInfo.componentStack}
                    </pre>
                  </>
                )}
              </div>
            )}
          </Result>
        </div>
      );
    }

    return children;
  }
}

// 功能性错误边界 - 用于特定场景
export const withErrorBoundary = <P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) => {
  const WrappedComponent: React.FC<P> = (props) => {
    return (
      <ErrorBoundary {...errorBoundaryProps}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name || 'Component'})`;

  return WrappedComponent;
};

export default ErrorBoundary;
