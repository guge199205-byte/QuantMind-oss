/**
 * 用户中心类型定义
 * 与后端API接口保持一致
 */

// ============ 用户档案相关类型 ============

export interface UserProfile {
  id: number;
  user_id: string;
  username: string;
  email: string;
  phone?: string;
  avatar?: string;
  bio?: string;
  location?: string;
  website?: string;
  trading_experience: 'beginner' | 'intermediate' | 'advanced';
  risk_tolerance: 'low' | 'medium' | 'high';
  investment_goals?: string;
  preferred_markets: string[];
  notification_settings: NotificationSettings;
  privacy_settings: PrivacySettings;
  created_at: string;
  updated_at: string;
}

export interface NotificationSettings {
  email_notifications: boolean;
  push_notifications: boolean;
  strategy_alerts: boolean;
  portfolio_updates: boolean;
  system_announcements: boolean;
  marketing_emails: boolean;
}

export interface PrivacySettings {
  profile_visibility: 'public' | 'private' | 'friends';
  show_email: boolean;
  show_phone: boolean;
  show_location: boolean;
  show_trading_stats: boolean;
  allow_messages: boolean;
}

export interface UserProfileUpdate {
  username?: string;
  email?: string;
  phone?: string;
  avatar?: string;
  bio?: string;
  location?: string;
  website?: string;
  trading_experience?: 'beginner' | 'intermediate' | 'advanced';
  risk_tolerance?: 'low' | 'medium' | 'high';
  investment_goals?: string;
  preferred_markets?: string[];
  notification_settings?: Partial<NotificationSettings>;
  privacy_settings?: Partial<PrivacySettings>;
}

// ============ 策略管理相关类型 ============

export type StrategyStatus =
  | 'draft'          // 草稿（AI刚生成，未回测）
  | 'repository'     // 仓库（回测通过，已保存）
  | 'live_trading'   // 实盘交易中
  | 'active'
  | 'inactive'
  | 'archived'
  | 'paused'
  | 'backtesting';

export interface UserStrategy {
  id: string;
  user_id: string;
  strategy_id: string;
  name: string;
  strategy_type: string;
  status: StrategyStatus;
  is_favorite: boolean;
  performance_summary: PerformanceSummary;
  last_backtest_id?: string;
  last_backtest_date?: string;
  notes?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  // 分享相关（新增）
  is_shared?: boolean;         // 是否已分享到社区
  share_post_id?: number;      // 关联的社区帖子ID
  share_count?: number;        // 分享次数
  source?: 'local' | 'community';  // 来源：本地创建 | 社区导入
  source_post_id?: number;     // 如果来自社区，记录原帖子ID

  // 生命周期管理相关（新增）
  code?: string;                      // 策略代码
  cos_url?: string;                   // COS存储地址
  code_hash?: string;                 // 代码哈希
  file_size?: number;                 // 文件大小
  validated_backtest_id?: number;     // 验证回测ID
  promoted_at?: string;               // 晋升到仓库的时间
  live_trading_started_at?: string;   // 实盘启动时间
}

export interface PerformanceSummary {
  total_return: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  avg_trade_duration: number;
  total_trades: number;
}

export interface StrategyManagementRequest {
  strategy_id: string;
  action: 'add' | 'remove' | 'favorite' | 'unfavorite' | 'archive' | 'enable' | 'disable';
  notes?: string;
  tags?: string[];
}

export interface StrategyUpdate {
  strategy_name?: string;
  strategy_type?: string;
  description?: string;
  status?: StrategyStatus;
  config?: Record<string, any>;
  is_favorite?: boolean;
  notes?: string;
  tags?: string[];
}

// ============ 投资组合相关类型 ============

export interface UserPortfolio {
  id: number;
  user_id: string;
  portfolio_name: string;
  description?: string;
  total_value: number;
  cash_balance: number;
  total_return: number;
  total_return_pct: number;
  positions: Position[];
  allocation: Allocation;
  risk_metrics: RiskMetrics;
  is_default: boolean;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  weight: number;
  asset_type: 'stock' | 'etf' | 'bond' | 'crypto' | 'other';
}

export interface Allocation {
  by_asset_type: Record<string, number>;
  by_sector: Record<string, number>;
  by_region: Record<string, number>;
}

export interface RiskMetrics {
  volatility: number;
  beta: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  var_95: number;
  cvar_95: number;
}

export interface PortfolioCreate {
  portfolio_name: string;
  description?: string;
  initial_cash: number;
  is_default?: boolean;
  is_public?: boolean;
}

export interface PortfolioUpdate {
  portfolio_name?: string;
  description?: string;
  is_public?: boolean;
}

// ============ 用户活动相关类型 ============

export interface UserActivity {
  id: number;
  user_id: string;
  activity_type: string;
  activity_data: Record<string, any>;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}

export interface ActivityFilter {
  activity_type?: string;
  limit?: number;
  offset?: number;
}

// ============ 数据同步相关类型 ============

export interface UserSyncRecord {
  id: number;
  user_id: string;
  sync_type: 'strategies' | 'portfolios' | 'preferences';
  sync_status: 'pending' | 'success' | 'failed';
  sync_data: Record<string, any>;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface SyncResult {
  synced_count: number;
  total_strategies?: number;
  total_portfolios?: number;
  sync_time: string;
  errors?: string[];
}

// ============ 用户配置相关类型 ============

export interface UserConfig {
  id: number;
  user_id: string;
  config_data: Record<string, any>;
  notification_settings: NotificationSettings;
  privacy_settings: PrivacySettings;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserConfigUpdate {
  config_data?: Record<string, any>;
  notification_settings?: Partial<NotificationSettings>;
  privacy_settings?: Partial<PrivacySettings>;
}

// ============ 头像管理相关类型 ============

export interface AvatarUploadResponse {
  success: boolean;
  avatar_url: string;
  file_key: string;
  file_size: number;
  upload_time: string;
  message?: string;
}

export interface AvatarInfo {
  user_id: string;
  avatar_url: string;
  has_custom_avatar: boolean;
  upload_time?: string;
  file_size?: number;
}

export interface AvatarUploadSettings {
  allowed_types: string[];
  max_size_mb: number;
  max_size_bytes: number;
  recommended_dimensions: {
    width: number;
    height: number;
    aspect_ratio: string;
  };
  supported_formats: Record<string, { description: string; quality: string }>;
  upload_tips: string[];
}

// ============ 用户认证相关类型 ============

export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

// ============ API响应类型 ============

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ============ 错误类型 ============

export interface ApiError {
  code: string;
  message: string;
  details?: any;
  timestamp?: string;
}

// ============ 状态类型 ============

export type LoadingState = 'idle' | 'loading' | 'success' | 'error';
export type OperationStatus = 'idle' | 'pending' | 'success' | 'error';

// ============ 工作空间相关类型（预留） ============

export interface Workspace {
  id: string;
  name: string;
  description?: string;
  user_id: string;
  team_id?: string;
  template_type: 'standard' | 'trading' | 'research' | 'analysis' | 'custom';
  layout: GridLayout;
  components: WorkspaceComponent[];
  settings: WorkspaceSettings;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface GridLayout {
  cols: number;
  rows: number;
  gap: number;
  items: GridItem[];
}

export interface GridItem {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  component_type: string;
}

export interface WorkspaceComponent {
  id: string;
  type: 'chart' | 'table' | 'text' | 'indicator' | 'filter' | 'calendar' | 'task';
  config: Record<string, any>;
  data_source?: string;
}

export interface WorkspaceSettings {
  theme: 'light' | 'dark' | 'auto';
  auto_save: boolean;
  grid_visible: boolean;
  snap_to_grid: boolean;
}

// ============ 版本控制相关类型（预留） ============

export interface ResourceVersion {
  id: string;
  resource_type: string;
  resource_id: string;
  version_number: number;
  commit_message: string;
  author_id: string;
  author_name: string;
  changes: VersionChange[];
  created_at: string;
}

export interface VersionChange {
  type: 'add' | 'modify' | 'delete';
  path: string;
  old_value?: any;
  new_value?: any;
}
