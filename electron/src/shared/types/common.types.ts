/**
 * 通用类型定义
 */

// API响应基础类型
export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  message?: string;
  code?: number;
}

// 分页响应类型
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// 错误类型
export interface IApiErrorType {
  code: string;
  message: string;
  details?: unknown;
}

// 错误类
export class ApiError extends Error {
  public readonly code: string;
  public readonly details?: unknown;

  constructor(data: IApiErrorType) {
    super(data.message);
    this.name = 'ApiError';
    this.code = data.code;
    this.details = data.details;
  }
}

// 保持向后兼容
export type ApiErrorType = ApiError;

// 请求配置类型
export interface RequestConfig {
  url: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  data?: unknown;
  params?: Record<string, unknown>;
  headers?: Record<string, string>;
  timeout?: number;
}

// 服务状态类型
export type ServiceStatus = 'idle' | 'loading' | 'success' | 'error';

// 主题类型
export type Theme = 'light' | 'dark' | 'auto';

// 语言类型
export type Language = 'zh-CN' | 'en-US';

// 用户角色类型
export type UserRole = 'admin' | 'user' | 'guest';

// 排序类型
export interface SortConfig {
  field: string;
  direction: 'asc' | 'desc';
}

// 过滤器类型
export interface FilterConfig {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'contains';
  value: unknown;
}

// 表格列配置类型
export interface TableColumn<T = unknown> {
  key: string;
  title: string;
  dataIndex?: keyof T;
  width?: number;
  align?: 'left' | 'center' | 'right';
  sorter?: boolean;
  filterable?: boolean;
  render?: (value: unknown, record: T, index: number) => React.ReactNode;
}

// 菜单项类型
export interface MenuItem {
  key: string;
  label: string;
  icon?: React.ReactNode;
  path?: string;
  children?: MenuItem[];
  permission?: string[];
}

// 通知类型
export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
  timestamp: number;
}

// 文件上传类型
export interface UploadFile {
  uid: string;
  name: string;
  status: 'uploading' | 'done' | 'error';
  url?: string;
  response?: unknown;
  error?: unknown;
}

// 图表数据类型
export interface ChartDataPoint {
  x: string | number;
  y: number;
  [key: string]: unknown;
}

// 时间范围类型
export interface TimeRange {
  start: Date;
  end: Date;
}

// 导出数据类型
export interface ExportConfig {
  format: 'csv' | 'excel' | 'json';
  fields?: string[];
  filename?: string;
}
