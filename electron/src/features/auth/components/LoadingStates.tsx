/**
 * 认证模块加载状态组件
 */

import React from 'react';
import { Spin, Card, Skeleton } from 'antd';

// 页面加载组件
export const PageLoading: React.FC<{ message?: string }> = ({ message = '加载中...' }) => {
  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <div style={{ textAlign: 'center', color: 'white' }}>
        <div style={{ height: 20 }} />
        <Spin size="large" />
        <div style={{ marginTop: '16px', fontSize: '16px' }}>{message}</div>
      </div>
    </div>
  );
};

// 表单加载组件
export const FormLoading: React.FC<{ message?: string }> = ({ message = '处理中...' }) => {
  return (
    <div style={{ textAlign: 'center', padding: '40px' }}>
      <Spin size="large" />
      <div style={{ marginTop: '16px', color: '#666' }}>{message}</div>
    </div>
  );
};

// 认证页面骨架屏
export const AuthPageSkeleton: React.FC = () => {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
        }}
        styles={{ body: { padding: '40px' } }}
      >
        {/* Logo 骨架屏 */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <Skeleton.Avatar size={64} style={{ margin: '0 auto 16px', display: 'block' }} />
          <Skeleton.Input
            style={{ width: 200, margin: '0 auto', display: 'block' }}
            active
          />
          <Skeleton.Input
            style={{ width: 120, margin: '8px auto 0', display: 'block' }}
            size="small"
            active
          />
        </div>

        {/* 表单字段骨架屏 */}
        <div style={{ marginBottom: '24px' }}>
          <Skeleton.Input
            style={{ width: '100%', marginBottom: '16px' }}
            size="large"
            active
          />
          <Skeleton.Input
            style={{ width: '100%', marginBottom: '16px' }}
            size="large"
            active
          />
        </div>

        {/* 按钮骨架屏 */}
        <Skeleton.Button
          style={{ width: '100%', height: '48px', marginBottom: '16px' }}
          size="large"
          active
        />

        {/* 底部链接骨架屏 */}
        <div style={{ textAlign: 'center' }}>
          <Skeleton.Input
            style={{ width: 150, margin: '0 auto' }}
            size="small"
            active
          />
        </div>
      </Card>
    </div>
  );
};

// 个人中心页面骨架屏
export const UserCenterSkeleton: React.FC = () => {
  return (
    <div style={{ padding: '24px' }}>
      {/* 用户信息卡片骨架屏 */}
      <Card style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Skeleton.Avatar size={80} />
          <div style={{ flex: 1 }}>
            <Skeleton.Input style={{ width: 200, marginBottom: 8 }} active />
            <Skeleton.Input style={{ width: 250, marginBottom: 12 }} size="small" active />
            <Skeleton.Button style={{ width: 80 }} size="small" active />
          </div>
          {[1, 2, 3].map((item) => (
            <div key={item} style={{ textAlign: 'center', padding: '0 24px', borderLeft: '1px solid #f0f0f0' }}>
              <Skeleton.Input style={{ width: 40, margin: '0 auto 4px' }} active />
              <Skeleton.Input style={{ width: 60, margin: '0 auto' }} size="small" active />
            </div>
          ))}
        </div>
      </Card>

      {/* 标签页骨架屏 */}
      <Card>
        <div style={{ marginBottom: 24 }}>
          {[1, 2, 3, 4].map((item) => (
            <Skeleton.Button
              key={item}
              style={{ marginRight: 16, width: 80 }}
              active
            />
          ))}
        </div>

        {/* 内容区域骨架屏 */}
        <div>
          {[1, 2, 3].map((item) => (
            <div key={item} style={{ marginBottom: 16 }}>
              <Skeleton.Input style={{ width: '100%', marginBottom: 8 }} active />
              <Skeleton.Input style={{ width: '80%', marginBottom: 8 }} size="small" active />
              <Skeleton.Input style={{ width: '60%' }} size="small" active />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default {
  PageLoading,
  FormLoading,
  AuthPageSkeleton,
  UserCenterSkeleton,
};
