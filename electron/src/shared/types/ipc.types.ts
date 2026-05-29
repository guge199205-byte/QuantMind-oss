/**
 * Electron IPC通信接口定义
 * 定义主进程与渲染进程之间的通信协议
 */

// IPC通道定义
export const IPC_CHANNELS = {
  // 数据库操作
  DB_QUERY: 'db:query',
  DB_INSERT: 'db:insert',
  DB_UPDATE: 'db:update',
  DB_DELETE: 'db:delete',
  DB_TRANSACTION: 'db:transaction',

  // 策略社区相关
  COMMUNITY_GET_STRATEGIES: 'community:get-strategies',
  COMMUNITY_CREATE_STRATEGY: 'community:create-strategy',
  COMMUNITY_UPDATE_STRATEGY: 'community:update-strategy',
  COMMUNITY_DELETE_STRATEGY: 'community:delete-strategy',
  COMMUNITY_GET_POSTS: 'community:get-posts',
  COMMUNITY_CREATE_POST: 'community:create-post',
  COMMUNITY_GET_COMMENTS: 'community:get-comments',
  COMMUNITY_CREATE_COMMENT: 'community:create-comment',
  COMMUNITY_FOLLOW_USER: 'community:follow-user',
  COMMUNITY_UNFOLLOW_USER: 'community:unfollow-user',
  COMMUNITY_GET_NOTIFICATIONS: 'community:get-notifications',
  COMMUNITY_MARK_NOTIFICATION_READ: 'community:mark-notification-read',

  // 用户相关
  USER_GET_PROFILE: 'user:get-profile',
  USER_UPDATE_PROFILE: 'user:update-profile',
  USER_GET_ACTIVITIES: 'user:get-activities',
  USER_GET_FAVORITES: 'user:get-favorites',
  USER_ADD_FAVORITE: 'user:add-favorite',
  USER_REMOVE_FAVORITE: 'user:remove-favorite',

  // 文件操作
  FILE_READ: 'file:read',
  FILE_WRITE: 'file:write',
  FILE_DELETE: 'file:delete',
  FILE_UPLOAD: 'file:upload',

  // 系统操作
  SYSTEM_GET_CONFIG: 'system:get-config',
  SYSTEM_SET_CONFIG: 'system:set-config',
  SYSTEM_GET_VERSION: 'system:get-version',
  SYSTEM_CHECK_UPDATE: 'system:check-update',

  // 通知
  NOTIFICATION_SHOW: 'notification:show',
  NOTIFICATION_SCHEDULE: 'notification:schedule',

  // 社区帖子操作
  COMMUNITY_UPDATE_POST: 'community:update-post',
  COMMUNITY_DELETE_POST: 'community:delete-post',
  COMMUNITY_UPDATE_COMMENT: 'community:update-comment',
  COMMUNITY_DELETE_COMMENT: 'community:delete-comment',
  COMMUNITY_GET_FOLLOWING_LIST: 'community:get-following-list',
  COMMUNITY_GET_FOLLOWERS_LIST: 'community:get-followers-list',
  COMMUNITY_MARK_ALL_NOTIFICATIONS_READ: 'community:mark-all-notifications-read',

  // 策略统计
  STRATEGY_GET_STATS: 'strategy:get-stats',
  STRATEGY_GET_RECOMMENDED: 'strategy:get-recommended',
  STRATEGY_GET_POPULAR: 'strategy:get-popular',

  // 用户搜索
  USER_SEARCH: 'user:search',

  // 用户统计
  USER_GET_STATS: 'user:get-stats',

  // 用户活动记录
  USER_RECORD_ACTIVITY: 'user:record-activity',

  // 缓存
  CACHE_GET: 'cache:get',
  CACHE_SET: 'cache:set',
  CACHE_CLEAR: 'cache:clear',

  // 同步
  SYNC_START: 'sync:start',
  SYNC_STATUS: 'sync:status',
  SYNC_CONFLICT_RESOLVE: 'sync:conflict-resolve',
} as const;

// IPC请求基础接口
export interface IPCRequest<T = any> {
  id: string;
  channel: string;
  data: T;
  timestamp: number;
}

// IPC响应基础接口
export interface IPCResponse<T = any> {
  id: string;
  success: boolean;
  data?: T;
  error?: IPCError;
  timestamp: number;
}

// IPC错误接口
export interface IPCError {
  code: string;
  message: string;
  details?: any;
  stack?: string;
}

// 数据库查询请求
export interface DBQueryRequest {
  sql: string;
  params?: any[];
  transaction?: boolean;
}

// 数据库查询响应
export interface DBQueryResponse {
  rows: any[];
  rowCount: number;
  lastInsertRowid?: number;
}

// 分页请求
export interface PaginatedRequest {
  page: number;
  size: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  filters?: Record<string, any>;
}

// 分页响应
export interface PaginatedResponse<T = any> {
  items: T[];
  total: number;
  page: number;
  size: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

// 策略过滤器
export interface StrategyFilter extends PaginatedRequest {
  userId?: number;
  type?: string;
  category?: string;
  riskLevel?: string;
  marketType?: string;
  isPublic?: boolean;
  isFeatured?: boolean;
  tags?: string[];
  keyword?: string;
}

// 帖子过滤器
export interface PostFilter extends PaginatedRequest {
  userId?: number;
  type?: 'discussion' | 'strategy' | 'question';
  tags?: string[];
  keyword?: string;
  isPinned?: boolean;
}

// 评论过滤器
export interface CommentFilter extends PaginatedRequest {
  strategyId?: number;
  postId?: number;
  userId?: number;
  parentId?: number | null;
}

// 用户活动过滤器
export interface ActivityFilter extends PaginatedRequest {
  userId?: number;
  activityType?: string;
  targetType?: string;
  startDate?: Date;
  endDate?: Date;
}

// 通知过滤器
export interface NotificationFilter extends PaginatedRequest {
  userId: number;
  type?: string;
  isRead?: boolean;
  startDate?: Date;
  endDate?: Date;
}

// 文件操作请求
export interface FileOperationRequest {
  path: string;
  encoding?: BufferEncoding;
  data?: string | Buffer;
}

// 文件操作响应
export interface FileOperationResponse {
  success: boolean;
  data?: string | Buffer;
  error?: string;
}

// 系统配置
export interface SystemConfig {
  theme: 'light' | 'dark' | 'auto';
  language: string;
  autoSync: boolean;
  syncInterval: number;
  cacheEnabled: boolean;
  cacheTtl: number;
  notificationsEnabled: boolean;
  autoUpdate: boolean;
}

// 同步状态
export interface SyncStatus {
  isRunning: boolean;
  lastSyncTime?: number;
  nextSyncTime?: number;
  progress?: number;
  status: 'idle' | 'syncing' | 'error' | 'completed';
  error?: string;
}

// 冲突解决
export interface ConflictResolution {
  strategy: 'local' | 'remote' | 'merge' | 'manual';
  resolution?: any;
}

// 错误码定义
export const IPC_ERROR_CODES = {
  // 通用错误
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
  INVALID_REQUEST: 'INVALID_REQUEST',
  TIMEOUT: 'TIMEOUT',

  // 数据库错误
  DB_CONNECTION_ERROR: 'DB_CONNECTION_ERROR',
  DB_QUERY_ERROR: 'DB_QUERY_ERROR',
  DB_TRANSACTION_ERROR: 'DB_TRANSACTION_ERROR',
  DB_CONSTRAINT_ERROR: 'DB_CONSTRAINT_ERROR',

  // 文件操作错误
  FILE_NOT_FOUND: 'FILE_NOT_FOUND',
  FILE_PERMISSION_ERROR: 'FILE_PERMISSION_ERROR',
  FILE_IO_ERROR: 'FILE_IO_ERROR',

  // 网络错误
  NETWORK_ERROR: 'NETWORK_ERROR',
  API_ERROR: 'API_ERROR',

  // 业务逻辑错误
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  NOT_FOUND: 'NOT_FOUND',
  VALIDATION_ERROR: 'VALIDATION_ERROR',

  // 同步错误
  SYNC_CONFLICT: 'SYNC_CONFLICT',
  SYNC_FAILED: 'SYNC_FAILED',
} as const;

// 工具函数
export function createIPCRequest<T>(channel: string, data: T): IPCRequest<T> {
  return {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    channel,
    data,
    timestamp: Date.now(),
  };
}

export function createIPCResponse<T>(
  requestId: string,
  success: boolean,
  data?: T,
  error?: IPCError
): IPCResponse<T> {
  return {
    id: requestId,
    success,
    data,
    error,
    timestamp: Date.now(),
  };
}

export function createIPCError(
  code: string,
  message: string,
  details?: any
): IPCError {
  return {
    code,
    message,
    details,
    stack: new Error().stack,
  };
}
