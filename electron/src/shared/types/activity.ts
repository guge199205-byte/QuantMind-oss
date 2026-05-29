/**
 * 用户活动类型定义
 * User Activity Types
 *
 * 统一的活动记录类型，支持个人中心和社区活动
 *
 * @author QuantMind Team
 * @date 2025-12-02
 */

/**
 * 活动类型枚举
 */
export enum ActivityType {
  // 策略相关
  STRATEGY_CREATE = 'strategy_create',       // 创建策略
  STRATEGY_UPDATE = 'strategy_update',       // 更新策略
  STRATEGY_DELETE = 'strategy_delete',       // 删除策略
  STRATEGY_SHARE = 'strategy_share',         // 分享策略
  STRATEGY_BACKTEST = 'strategy_backtest',   // 回测策略

  // 组合相关
  PORTFOLIO_CREATE = 'portfolio_create',     // 创建组合
  PORTFOLIO_UPDATE = 'portfolio_update',     // 更新组合
  PORTFOLIO_DELETE = 'portfolio_delete',     // 删除组合

  // 社区相关
  POST_CREATE = 'post_create',               // 发布帖子
  POST_COMMENT = 'post_comment',             // 评论帖子
  POST_LIKE = 'post_like',                   // 点赞帖子
  POST_COLLECT = 'post_collect',             // 收藏帖子
  COMMENT_LIKE = 'comment_like',             // 点赞评论

  // 策略社区互动
  STRATEGY_IMPORT = 'strategy_import',       // 导入社区策略
  STRATEGY_FOLLOW = 'strategy_follow',       // 关注策略
}

/**
 * 活动来源
 */
export enum ActivitySource {
  USER_CENTER = 'user_center',    // 个人中心
  COMMUNITY = 'community',        // 策略社区
  BACKTEST = 'backtest',          // 回测系统
  TRADING = 'trading',            // 交易系统
}

/**
 * 活动记录基础接口
 */
export interface BaseActivity {
  id: string;
  user_id: string;
  type: ActivityType;
  source: ActivitySource;
  title: string;
  description?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

/**
 * 策略活动
 */
export interface StrategyActivity extends BaseActivity {
  type: ActivityType.STRATEGY_CREATE | ActivityType.STRATEGY_UPDATE |
        ActivityType.STRATEGY_DELETE | ActivityType.STRATEGY_SHARE |
        ActivityType.STRATEGY_BACKTEST | ActivityType.STRATEGY_IMPORT;
  metadata: {
    strategy_id: string;
    strategy_name: string;
    strategy_type?: string;
    performance?: {
      return_pct?: number;
      sharpe_ratio?: number;
    };
  };
}

/**
 * 组合活动
 */
export interface PortfolioActivity extends BaseActivity {
  type: ActivityType.PORTFOLIO_CREATE | ActivityType.PORTFOLIO_UPDATE |
        ActivityType.PORTFOLIO_DELETE;
  metadata: {
    portfolio_id: string;
    portfolio_name: string;
    total_value?: number;
  };
}

/**
 * 社区帖子活动
 */
export interface PostActivity extends BaseActivity {
  type: ActivityType.POST_CREATE | ActivityType.POST_COMMENT |
        ActivityType.POST_LIKE | ActivityType.POST_COLLECT;
  metadata: {
    post_id: number;
    post_title: string;
    post_category?: string;
    comment_content?: string;  // 如果是评论
  };
}

/**
 * 联合活动类型
 */
export type Activity = StrategyActivity | PortfolioActivity | PostActivity | BaseActivity;

/**
 * 活动列表响应
 */
export interface ActivitiesResponse {
  activities: Activity[];
  pagination: {
    current: number;
    page_size: number;
    total: number;
    has_more: boolean;
  };
}

/**
 * 活动分组（按日期）
 */
export interface ActivityGroup {
  date: string;          // YYYY-MM-DD
  dateLabel: string;     // "今天", "昨天", "2025-12-01"
  activities: Activity[];
}

/**
 * 活动统计
 */
export interface ActivityStats {
  total_count: number;
  today_count: number;
  week_count: number;
  month_count: number;
  by_type: Record<ActivityType, number>;
  by_source: Record<ActivitySource, number>;
}

/**
 * 活动图标映射
 */
export const ACTIVITY_ICONS: Record<ActivityType, string> = {
  [ActivityType.STRATEGY_CREATE]: '📝',
  [ActivityType.STRATEGY_UPDATE]: '✏️',
  [ActivityType.STRATEGY_DELETE]: '🗑️',
  [ActivityType.STRATEGY_SHARE]: '🔗',
  [ActivityType.STRATEGY_BACKTEST]: '📊',
  [ActivityType.STRATEGY_IMPORT]: '📥',
  [ActivityType.STRATEGY_FOLLOW]: '⭐',
  [ActivityType.PORTFOLIO_CREATE]: '💼',
  [ActivityType.PORTFOLIO_UPDATE]: '📝',
  [ActivityType.PORTFOLIO_DELETE]: '🗑️',
  [ActivityType.POST_CREATE]: '✍️',
  [ActivityType.POST_COMMENT]: '💬',
  [ActivityType.POST_LIKE]: '❤️',
  [ActivityType.POST_COLLECT]: '⭐',
  [ActivityType.COMMENT_LIKE]: '👍',
};

/**
 * 活动颜色映射
 */
export const ACTIVITY_COLORS: Record<ActivityType, string> = {
  [ActivityType.STRATEGY_CREATE]: '#52c41a',
  [ActivityType.STRATEGY_UPDATE]: '#1890ff',
  [ActivityType.STRATEGY_DELETE]: '#f5222d',
  [ActivityType.STRATEGY_SHARE]: '#722ed1',
  [ActivityType.STRATEGY_BACKTEST]: '#fa8c16',
  [ActivityType.STRATEGY_IMPORT]: '#13c2c2',
  [ActivityType.STRATEGY_FOLLOW]: '#faad14',
  [ActivityType.PORTFOLIO_CREATE]: '#52c41a',
  [ActivityType.PORTFOLIO_UPDATE]: '#1890ff',
  [ActivityType.PORTFOLIO_DELETE]: '#f5222d',
  [ActivityType.POST_CREATE]: '#722ed1',
  [ActivityType.POST_COMMENT]: '#1890ff',
  [ActivityType.POST_LIKE]: '#eb2f96',
  [ActivityType.POST_COLLECT]: '#faad14',
  [ActivityType.COMMENT_LIKE]: '#52c41a',
};

/**
 * 活动文本映射
 */
export const ACTIVITY_TEXTS: Record<ActivityType, string> = {
  [ActivityType.STRATEGY_CREATE]: '创建了策略',
  [ActivityType.STRATEGY_UPDATE]: '更新了策略',
  [ActivityType.STRATEGY_DELETE]: '删除了策略',
  [ActivityType.STRATEGY_SHARE]: '分享了策略',
  [ActivityType.STRATEGY_BACKTEST]: '回测了策略',
  [ActivityType.STRATEGY_IMPORT]: '导入了策略',
  [ActivityType.STRATEGY_FOLLOW]: '关注了策略',
  [ActivityType.PORTFOLIO_CREATE]: '创建了组合',
  [ActivityType.PORTFOLIO_UPDATE]: '更新了组合',
  [ActivityType.PORTFOLIO_DELETE]: '删除了组合',
  [ActivityType.POST_CREATE]: '发布了帖子',
  [ActivityType.POST_COMMENT]: '评论了帖子',
  [ActivityType.POST_LIKE]: '点赞了帖子',
  [ActivityType.POST_COLLECT]: '收藏了帖子',
  [ActivityType.COMMENT_LIKE]: '点赞了评论',
};

/**
 * 工具函数：格式化活动时间
 */
export function formatActivityTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;

  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

/**
 * 工具函数：按日期分组活动
 */
export function groupActivitiesByDate(activities: Activity[]): ActivityGroup[] {
  const groups: Map<string, Activity[]> = new Map();
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  activities.forEach(activity => {
    const activityDate = new Date(activity.created_at);
    const dateKey = activityDate.toISOString().split('T')[0];

    if (!groups.has(dateKey)) {
      groups.set(dateKey, []);
    }
    groups.get(dateKey)!.push(activity);
  });

  const result: ActivityGroup[] = [];

  Array.from(groups.entries())
    .sort(([a], [b]) => b.localeCompare(a))
    .forEach(([date, acts]) => {
      let dateLabel = date;
      const actDate = new Date(date);

      if (actDate.toDateString() === today.toDateString()) {
        dateLabel = '今天';
      } else if (actDate.toDateString() === yesterday.toDateString()) {
        dateLabel = '昨天';
      }

      result.push({
        date,
        dateLabel,
        activities: acts.sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        ),
      });
    });

  return result;
}

/**
 * 工具函数：获取活动图标
 */
export function getActivityIcon(type: ActivityType): string {
  return ACTIVITY_ICONS[type] || '📌';
}

/**
 * 工具函数：获取活动颜色
 */
export function getActivityColor(type: ActivityType): string {
  return ACTIVITY_COLORS[type] || '#1890ff';
}

/**
 * 工具函数：获取活动文本
 */
export function getActivityText(type: ActivityType): string {
  return ACTIVITY_TEXTS[type] || '进行了操作';
}
