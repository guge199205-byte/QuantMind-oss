/**
 * 用户中心Store配置
 * 整合所有用户中心相关的Redux slices
 */

import { configureStore, combineReducers } from '@reduxjs/toolkit';
import profileReducer from './profileSlice';
import strategiesReducer from './strategiesSlice';
import portfoliosReducer from './portfoliosSlice';
import configReducer from './configSlice';

// ============ 根Reducer ============

const userCenterReducer = combineReducers({
  profile: profileReducer,
  strategies: strategiesReducer,
  portfolios: portfoliosReducer,
  config: configReducer,
});

// ============ Store配置 ============

export const createUserCenterStore = () => {
  return configureStore({
    reducer: userCenterReducer,
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({
        serializableCheck: {
          // 忽略某些action类型的序列化检查（如文件上传）
          ignoredActions: ['profile/uploadAvatar/pending'],
          ignoredPaths: ['profile.avatarUploadProgress'],
        },
      }),
    devTools: process.env.NODE_ENV !== 'production',
  });
};

// ============ 类型定义 ============

export type UserCenterStore = ReturnType<typeof createUserCenterStore>;
export type UserCenterRootState = ReturnType<typeof userCenterReducer>;
export type UserCenterDispatch = UserCenterStore['dispatch'];

// ============ 导出Reducer（用于集成到主Store） ============

export default userCenterReducer;
