/**
 * 设置中心页面
 */

import React from 'react';
import { useUserConfig, useNotificationSettings, usePrivacySettings } from '../hooks';
import { Form, Switch, message, Spin, Alert } from 'antd';
import { Bell, ShieldCheck, Mail, Smartphone, Zap, Globe, MessageCircle, BarChart3, Users, RefreshCw } from 'lucide-react';

interface SettingsPageProps {
  userId: string;
}

const SettingsPage: React.FC<SettingsPageProps> = ({ userId }) => {
  const { config, isLoading, error } = useUserConfig(userId);
  const {
    settings: notificationSettings,
    updateSettings: updateNotificationSettings,
    updateStatus: notificationUpdateStatus,
  } = useNotificationSettings(userId);
  const {
    settings: privacySettings,
    updateSettings: updatePrivacySettings,
    updateStatus: privacyUpdateStatus,
  } = usePrivacySettings(userId);

  const handleNotificationChange = async (key: string, value: boolean) => {
    try {
      await updateNotificationSettings({
        [key]: value,
      });
      message.success('通知设置已更新');
    } catch (err: any) {
      message.error(err.message || '更新失败');
    }
  };

  const handlePrivacyChange = async (key: string, value: boolean | string) => {
    try {
      await updatePrivacySettings({
        [key]: value,
      });
      message.success('隐私设置已更新');
    } catch (err: any) {
      message.error(err.message || '更新失败');
    }
  };

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" tip="加载中...">
          <div style={{ height: 100 }} />
        </Spin>
      </div>
    );
  }

  if (error) {
    return <Alert message="错误" description={error} type="error" showIcon />;
  }

  return (
    <div className="settings-page max-w-4xl mx-auto space-y-8">
      {/* 通知设置 */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100 bg-slate-50/50 flex items-center gap-3">
          <Bell className="w-5 h-5 text-blue-500" />
          <h2 className="text-base font-black text-slate-800 uppercase tracking-widest">通知设置</h2>
        </div>
        <div className="p-8">
          <Form layout="vertical" className="space-y-6">
            <div className="flex items-center justify-between p-4 bg-slate-50/50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-white border border-slate-100 flex items-center justify-center text-blue-500">
                  <Mail className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-700">邮件通知</div>
                  <p className="text-xs text-slate-400 font-medium mt-0.5">接收策略执行和系统重要事件的邮件提醒</p>
                </div>
              </div>
              <Switch
                checked={notificationSettings?.email_notifications}
                onChange={(checked) => handleNotificationChange('email_notifications', checked)}
                loading={notificationUpdateStatus === 'loading'}
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50/50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-white border border-slate-100 flex items-center justify-center text-indigo-500">
                  <Zap className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-700">推送通知</div>
                  <p className="text-xs text-slate-400 font-medium mt-0.5">在桌面或移动端接收实时操作推送</p>
                </div>
              </div>
              <Switch
                checked={notificationSettings?.push_notifications}
                onChange={(checked) => handleNotificationChange('push_notifications', checked)}
                loading={notificationUpdateStatus === 'loading'}
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50/50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-white border border-slate-100 flex items-center justify-center text-emerald-500">
                  <Smartphone className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-700">策略状态监控</div>
                  <p className="text-xs text-slate-400 font-medium mt-0.5">当您的量化策略状态发生变化时立即通知</p>
                </div>
              </div>
              <Switch
                checked={notificationSettings?.strategy_alerts}
                onChange={(checked) => handleNotificationChange('strategy_alerts', checked)}
                loading={notificationUpdateStatus === 'loading'}
              />
            </div>
          </Form>
        </div>
      </div>

      {/* 隐私设置 */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100 bg-slate-50/50 flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-emerald-500" />
          <h2 className="text-base font-black text-slate-800 uppercase tracking-widest">隐私与安全控制</h2>
        </div>
        <div className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="flex items-center justify-between p-4 bg-slate-50/50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-3">
                <Globe className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-bold text-slate-700">公开个人位置</span>
              </div>
              <Switch
                checked={privacySettings?.show_location}
                onChange={(checked) => handlePrivacyChange('show_location', checked)}
                loading={privacyUpdateStatus === 'loading'}
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50/50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-3">
                <BarChart3 className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-bold text-slate-700">公开交易统计</span>
              </div>
              <Switch
                checked={privacySettings?.show_trading_stats}
                onChange={(checked) => handlePrivacyChange('show_trading_stats', checked)}
                loading={privacyUpdateStatus === 'loading'}
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50/50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-3">
                <MessageCircle className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-bold text-slate-700">允许站内私信</span>
              </div>
              <Switch
                checked={privacySettings?.allow_messages}
                onChange={(checked) => handlePrivacyChange('allow_messages', checked)}
                loading={privacyUpdateStatus === 'loading'}
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50/50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-3">
                <Users className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-bold text-slate-700">显示社交动态</span>
              </div>
              <Switch
                checked={true}
                onChange={() => { }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
