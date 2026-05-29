/**
 * MFA (多因素认证) 设置页面
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Switch,
  Steps,
  QRCode,
  Input,
  message,
  Alert,
  Space,
  Divider,
  Modal,
  List,
  Tag,
} from 'antd';
import {
  SafetyOutlined,
  QrcodeOutlined,
  KeyOutlined,
  CheckCircleOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { SERVICE_ENDPOINTS } from '../../../config/services';

const { Step } = Steps;

interface MFASettingsPageProps {
  userId: string;
}

import { ShieldCheck, ShieldAlert, Smartphone, Key, Download, Info } from 'lucide-react';

const MFASettingsPage: React.FC<MFASettingsPageProps> = ({ userId }) => {
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [setupStep, setSetupStep] = useState(0);
  const [qrCodeUrl, setQrCodeUrl] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [setupModalVisible, setSetupModalVisible] = useState(false);

  useEffect(() => {
    checkMFAStatus();
  }, [userId]);

  const API_BASE = SERVICE_ENDPOINTS.USER_SERVICE;

  const checkMFAStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/users/${userId}/mfa/status`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setMfaEnabled(data.data.enabled);
      }
    } catch (error) {
      console.error('检查MFA状态失败:', error);
    }
  };

  const handleEnableMFA = async () => {
    setSetupModalVisible(true);
    setSetupStep(0);
    await initiateMFASetup();
  };

  const initiateMFASetup = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/${userId}/mfa/setup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('启动MFA设置失败');
      }

      const data = await response.json();
      setQrCodeUrl(data.data.qr_code_url);
      setSecretKey(data.data.secret_key);
      setSetupStep(1);
    } catch (error: any) {
      message.error(error.message || '设置失败');
      setSetupModalVisible(false);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyMFA = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      message.error('请输入6位验证码');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/${userId}/mfa/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          code: verificationCode,
        }),
      });

      if (!response.ok) {
        throw new Error('验证码错误');
      }

      const data = await response.json();
      setBackupCodes(data.data.backup_codes);
      setSetupStep(2);
      message.success('MFA启用成功');
    } catch (error: any) {
      message.error(error.message || '验证失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDisableMFA = async () => {
    Modal.confirm({
      title: '确认禁用MFA?',
      content: '禁用多因素认证将降低您的账户安全性。',
      okText: '确认禁用',
      cancelText: '取消',
      okButtonProps: { danger: true, className: 'rounded-xl font-bold' },
      cancelButtonProps: { className: 'rounded-xl font-bold' },
      onOk: async () => {
        setLoading(true);
        try {
          const response = await fetch(`${API_BASE}/users/${userId}/mfa/disable`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${localStorage.getItem('access_token')}`,
            },
          });

          if (!response.ok) {
            throw new Error('禁用MFA失败');
          }

          setMfaEnabled(false);
          message.success('MFA已禁用');
        } catch (error: any) {
          message.error(error.message || '操作失败');
        } finally {
          setLoading(false);
        }
      },
    });
  };

  const handleFinishSetup = () => {
    setSetupModalVisible(false);
    setMfaEnabled(true);
    setVerificationCode('');
    setSetupStep(0);
    checkMFAStatus();
  };

  const downloadBackupCodes = () => {
    const content = backupCodes.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mfa-backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100 bg-slate-50/50 flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-indigo-500" />
          <h2 className="text-base font-black text-slate-800 uppercase tracking-widest">多因素认证 (MFA)</h2>
        </div>

        <div className="p-8">
          <div className="bg-blue-50 p-4 rounded-xl flex items-start gap-3 border border-blue-100 mb-8">
            <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
            <div className="text-xs text-blue-700 leading-relaxed font-medium">
              多因素认证为您的账户添加额外的安全层。即使密码泄露，他人也无法通过验证码壁垒登录您的账户。
            </div>
          </div>

          <div className="flex items-center justify-between p-6 bg-slate-50/50 rounded-2xl border border-slate-100">
            <div>
              <div className="mb-2">
                {mfaEnabled ? (
                  <span className="px-3 py-1 bg-emerald-50 text-emerald-600 rounded-xl text-[10px] font-black uppercase tracking-widest border border-emerald-100 flex items-center gap-1.5 w-fit">
                    <ShieldCheck className="w-3.5 h-3.5" /> 已启用保护
                  </span>
                ) : (
                  <span className="px-3 py-1 bg-slate-100 text-slate-400 rounded-xl text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5 w-fit">
                    <ShieldAlert className="w-3.5 h-3.5" /> 未启用
                  </span>
                )}
              </div>
              <div className="text-sm font-bold text-slate-600 mt-3">
                {mfaEnabled
                  ? '您的账户目前处于高等级安全保护状态'
                  : '启用 MFA 认证可将账户被盗风险降低 99%'}
              </div>
            </div>

            {mfaEnabled ? (
              <button
                onClick={handleDisableMFA}
                className="px-6 py-2 bg-rose-50 text-rose-600 border border-rose-100 rounded-xl font-bold text-sm hover:bg-rose-100 transition-all"
              >
                禁用 MFA
              </button>
            ) : (
              <button
                onClick={handleEnableMFA}
                className="px-8 py-2 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-black text-sm shadow-md hover:shadow-lg transition-all active:scale-95"
              >
                立即启用
              </button>
            )}
          </div>

          <div className="mt-10 pt-8 border-t border-gray-100">
            <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-6 flex items-center gap-2">
              <Smartphone className="w-4 h-4" /> 快速操作指南
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center font-black text-slate-300 shrink-0">1</div>
                <p className="text-xs text-slate-500 font-medium leading-relaxed">下载验证器应用 (推荐: Google Authenticator, Microsoft Authenticator)</p>
              </div>
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center font-black text-slate-300 shrink-0">2</div>
                <p className="text-xs text-slate-500 font-medium leading-relaxed">在应用中扫描本站提供的专属安全二维码</p>
              </div>
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center font-black text-slate-300 shrink-0">3</div>
                <p className="text-xs text-slate-500 font-medium leading-relaxed">输入由验证器每 30 秒生成的 6 位动态验证码</p>
              </div>
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center font-black text-slate-300 shrink-0">4</div>
                <p className="text-xs text-slate-500 font-medium leading-relaxed">妥善保存下载的备份码，以防手机丢失无法登录</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* MFA设置对话框 */}
      <Modal
        title={
          <div className="flex items-center gap-2">
            <Key className="w-5 h-5 text-blue-500" />
            <span className="font-black text-slate-800">设置多因素认证</span>
          </div>
        }
        open={setupModalVisible}
        onCancel={() => setSetupModalVisible(false)}
        footer={null}
        width={600}
        destroyOnHidden
        className="custom-modern-modal"
      >
        <div className="py-4">
          <Steps current={setupStep} className="mb-10 custom-modern-steps" size="small">
            <Step title="身份确认" />
            <Step title="扫描验证" />
            <Step title="保存备份" />
          </Steps>

          {setupStep === 0 && (
            <div className="text-center py-8">
              <div className="w-20 h-20 bg-blue-50 rounded-3xl flex items-center justify-center mx-auto mb-6">
                <ShieldCheck className="w-10 h-10 text-blue-500" />
              </div>
              <h3 className="text-xl font-black text-slate-800 mb-2">增强账户安全</h3>
              <p className="text-sm text-slate-400 font-medium mb-8 px-12">
                我们采用工业级安全标准，确保您的量化资产和策略配置始终处于最高安全级别。
              </p>
              <button
                onClick={initiateMFASetup}
                className="px-10 py-3 bg-slate-900 text-white rounded-xl font-black text-sm hover:bg-slate-800 shadow-xl transition-all active:scale-95"
              >
                开启设置流程
              </button>
            </div>
          )}

          {setupStep === 1 && (
            <div className="space-y-8">
              <div className="text-center">
                <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-6">Scan with Auth App</h4>
                {qrCodeUrl && (
                  <div className="inline-block p-4 bg-white border border-slate-100 rounded-2xl shadow-xl">
                    <QRCode value={qrCodeUrl} size={180} bordered={false} />
                  </div>
                )}
              </div>

              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2 px-1">Manual Setup Key</span>
                <code className="block p-3 bg-white border border-slate-100 rounded-lg text-xs font-mono font-bold text-indigo-600 break-all">
                  {secretKey}
                </code>
              </div>

              <div className="space-y-4">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block px-1">
                  6-Digit Verification Code
                </label>
                <Input
                  size="large"
                  placeholder="000 000"
                  maxLength={6}
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                  className="rounded-xl border-gray-200 text-center text-3xl font-black font-mono tracking-[0.5em] h-16 focus:ring-4 focus:ring-blue-500/10"
                />
                <button
                  onClick={handleVerifyMFA}
                  disabled={verificationCode.length !== 6 || loading}
                  className="w-full py-4 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-black text-sm shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all active:scale-[0.98]"
                >
                  {loading ? '正在验证核心密钥...' : '完成扫码并验证'}
                </button>
              </div>
            </div>
          )}

          {setupStep === 2 && (
            <div className="space-y-8">
              <div className="bg-emerald-50 p-4 rounded-xl flex items-start gap-3 border border-emerald-100">
                <ShieldCheck className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                <div className="text-xs text-emerald-700 leading-relaxed font-bold">
                  MFA 已成功启用！请将以下备份码保存在安全的地方（如 1Password 或 纸质文档）。
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-slate-50/50">
                  <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Single-Use Backup Codes</span>
                  <button
                    onClick={downloadBackupCodes}
                    className="flex items-center gap-1.5 text-[10px] font-black text-blue-500 hover:text-blue-600 uppercase transition-all"
                  >
                    <Download className="w-3 h-3" /> Save as TXT
                  </button>
                </div>
                <div className="p-6 grid grid-cols-2 gap-3">
                  {backupCodes.map((code) => (
                    <code key={code} className="p-2 bg-slate-50 border border-slate-100 rounded-lg text-center font-mono font-bold text-slate-600 text-sm">
                      {code}
                    </code>
                  ))}
                </div>
              </div>

              <button
                onClick={handleFinishSetup}
                className="w-full py-4 bg-slate-900 text-white rounded-xl font-black text-sm hover:bg-slate-800 shadow-xl transition-all active:scale-[0.98]"
              >
                进入受保护的仪表盘
              </button>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default MFASettingsPage;
