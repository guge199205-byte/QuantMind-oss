/**
 * Feedback组件导出
 * 包含加载状态、错误处理、进度条等反馈组件
 */

// Skeleton加载组件
export {
  TableSkeleton,
  ChartSkeleton,
  CardSkeleton,
  ListSkeleton,
  DashboardSkeleton,
  DetailSkeleton,
  SkeletonWrapper
} from './SkeletonLoader';

// 进度条组件
export {
  TopProgressBar,
  CircularProgress,
  StepProgress,
  MultiProgress,
  LabeledProgress,
  DashboardProgress,
  LoadingProgress,
  FullscreenProgress
} from './ProgressBar';

// 错误边界
export {
  ErrorBoundary,
  withErrorBoundary
} from './ErrorBoundary';

// 错误提示
export {
  ErrorMessage,
  NetworkError,
  DataError,
  PermissionError,
  TimeoutError,
  SimpleError,
  InlineError
} from './ErrorMessage';

export type { ErrorType } from './ErrorMessage';
