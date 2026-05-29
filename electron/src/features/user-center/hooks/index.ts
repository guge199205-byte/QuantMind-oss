/**
 * 用户中心Hooks统一导出
 */

// Profile hooks
export {
  useProfile,
  useAvatarUpload,
} from './useProfile';

// Strategies hooks
export {
  useStrategies,
  useStrategy,
  useCreateStrategy,
  useDeleteStrategy,
} from './useStrategies';

// Portfolios hooks
export {
  usePortfolios,
  usePortfolio,
  useCreatePortfolio,
} from './usePortfolios';

// Config hooks
export {
  useUserConfig,
  useNotificationSettings,
  usePrivacySettings,
} from './useConfig';
