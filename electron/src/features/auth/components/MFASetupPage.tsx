/**
 * 多因素认证设置页面
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Steps,
  Row,
  Col,
  Typography,
  Alert,
  Button,
  Input,
  Space,
  Divider,
  Badge,
  Modal,
  List,
  Tooltip,
  message,
  Spin,
} from 'antd';
import {
  QrcodeOutlined,
  KeyOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  ExclamationCircleOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  MobileOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../store';
import { mfaService } from '../services/mfaService';
import { authService } from '../services/authService';

const { Title, Text, Paragraph } = Typography;
const { Step } = Steps;

interface MFASetupData {
  secret: string;
  qr_code: string;
  backup_codes: string[];
  manual_entry_key: string;
  instructions: {
    step1: string;
    step2: string;
    step3: string;
    step4: string;
  };
}

const MFASetupPage: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [mfaData, setMfaData] = useState<MFASetupData | null>(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [showBackupCodes, setShowBackupCodes] = useState(false);
  const [backupCodesCopied, setBackupCodesCopied] = useState(false);
  const [mfaEnabled, setMfaEnabled] = useState(false);

  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { user } = useAppSelector(state => state.auth);

  useEffect(() => {
    checkMFAStatus();
  }, []);

  const checkMFAStatus = async () => {
    try {
      const response = await mfaService.getMFAStatus();
      if (response.success) {
        setMfaEnabled(response.data.enabled);
        if (response.data.enabled) {
          // 如果已经启用MFA，跳转到MFA管理页面
          navigate('/user-center/security/mfa/manage');
        }
      }
    } catch (error) {
      console.error('检查MFA状态失败:', error);
    }
  };

  const handleSetupMFA = async () => {
    setLoading(true);
    try {
      const response = await mfaService.setupMFA();
      if (response.success) {
        setMfaData(response.data);
        setCurrentStep(1);
        message.success('MFA设置已准备就绪');
      } else {
        message.error(response.message || 'MFA设置失败');
      }
    } catch (error) {
      console.error('MFA设置失败:', error);
      message.error('MFA设置失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyAndEnable = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      message.error('请输入6位验证码');
      return;
    }

    setLoading(true);
    try {
      const response = await mfaService.verifyAndEnableMFA({
        verification_code: verificationCode,
      });

      if (response.data.success) {
        setMfaEnabled(true);
        setCurrentStep(3);
        message.success('多因素认证已成功启用');

        // 3秒后跳转到管理页面
        setTimeout(() => {
          navigate('/user-center/security/mfa/manage');
        }, 3000);
      } else {
        message.error(response.data.message || '验证失败');
      }
    } catch (error) {
      console.error('MFA验证失败:', error);
      message.error('验证失败，请检查验证码');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string, type: string) => {
    try {
      await navigator.clipboard.writeText(text);
      message.success(`${type}已复制到剪贴板`);
      if (type === '备用恢复码') {
        setBackupCodesCopied(true);
      }
    } catch (error) {
      message.error('复制失败');
    }
  };

  const downloadBackupCodes = () => {
    if (!mfaData) return;

    const content = `
QuantMind量化交易平台 - MFA备用恢复码

重要提示：请将这些备用恢复码保存在安全的地方。
当您无法使用认证应用时，可以使用这些代码登录。

用户：${user?.email}
生成时间：${new Date().toLocaleString()}

备用恢复码：
${mfaData.backup_codes.map((code, index) => `${index + 1}. ${code}`).join('\n')}

⚠️ 每个备用码只能使用一次
⚠️ 请勿与他人分享这些代码
⚠️ 建议将代码打印或保存在离线安全的地方
    `.trim();

    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `QuantMind_MFA_Backup_Codes_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    message.success('备用恢复码已下载');
  };

  const steps = [
    {
      title: '开始设置',
      icon: <SafetyCertificateOutlined />,
      description: '了解多因素认证',
    },
    {
      title: '扫描二维码',
      icon: <QrcodeOutlined />,
      description: '使用认证应用扫描',
    },
    {
      title: '验证设置',
      icon: <KeyOutlined />,
      description: '输入验证码确认',
    },
    {
      title: '完成设置',
      icon: <CheckCircleOutlined />,
      description: 'MFA启用成功',
    },
  ];

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Card className="setup-card">
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <SafetyCertificateOutlined style={{ fontSize: '64px', color: '#1890ff', marginBottom: '24px' }} />
              <Title level={3}>启用多因素认证</Title>
              <Paragraph style={{ fontSize: '16px', color: '#666', maxWidth: '500px', margin: '0 auto 32px' }}>
                多因素认证(MFA)为您的账户提供额外的安全保护。启用后，登录时除了密码外，
                还需要提供来自认证应用的验证码。
              </Paragraph>

              <Alert
                message="安全提示"
                description={
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    <li>请确保您的手机已安装Google Authenticator或类似应用</li>
                    <li>设置过程中生成的备用恢复码请妥善保存</li>
                    <li>备用恢复码是在无法使用认证应用时的最后手段</li>
                  </ul>
                }
                type="info"
                showIcon
                style={{ marginBottom: '32px', textAlign: 'left' }}
              />

              <Button
                type="primary"
                size="large"
                onClick={handleSetupMFA}
                loading={loading}
                icon={<SafetyCertificateOutlined />}
              >
                开始设置MFA
              </Button>
            </div>
          </Card>
        );

      case 1:
        return (
          <Card className="setup-card">
            <Row gutter={[32, 32]}>
              <Col xs={24} md={12}>
                <div style={{ textAlign: 'center' }}>
                  <Title level={4}>扫描二维码</Title>
                  <Paragraph style={{ color: '#666' }}>
                    使用Google Authenticator等应用扫描下方二维码
                  </Paragraph>

                  {mfaData?.qr_code && (
                    <div style={{
                      background: '#fff',
                      padding: '20px',
                      borderRadius: '8px',
                      border: '1px solid #d9d9d9',
                      display: 'inline-block',
                      margin: '16px 0'
                    }}>
                      <img
                        src={mfaData.qr_code}
                        alt="MFA QR Code"
                        style={{
                          width: '200px',
                          height: '200px',
                          display: 'block'
                        }}
                      />
                    </div>
                  )}

                  <div style={{ marginTop: '24px' }}>
                    <Text type="secondary">或手动输入密钥：</Text>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      marginTop: '8px'
                    }}>
                      <Input.Password
                        value={mfaData?.manual_entry_key}
                        readOnly
                        style={{ fontFamily: 'monospace' }}
                        iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
                      />
                      <Tooltip title="复制密钥">
                        <Button
                          icon={<CopyOutlined />}
                          onClick={() => mfaData && copyToClipboard(mfaData.manual_entry_key, '密钥')}
                        />
                      </Tooltip>
                    </div>
                  </div>
                </div>
              </Col>

              <Col xs={24} md={12}>
                <div>
                  <Title level={4}>
                    备用恢复码
                    <Badge
                      count={mfaData?.backup_codes.length}
                      style={{ marginLeft: '8px' }}
                    />
                  </Title>
                  <Paragraph style={{ color: '#666' }}>
                    请安全保存这些备用恢复码，每个代码只能使用一次
                  </Paragraph>

                  <Alert
                    message="重要"
                    description="备用恢复码是您无法使用认证应用时的最后手段，请务必妥善保存"
                    type="warning"
                    showIcon
                    style={{ marginBottom: '16px' }}
                  />

                  <div style={{
                    background: '#fafafa',
                    padding: '16px',
                    borderRadius: '6px',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                    maxHeight: '200px',
                    overflowY: 'auto'
                  }}>
                    {showBackupCodes ? (
                      <List
                        size="small"
                        dataSource={mfaData?.backup_codes || []}
                        renderItem={(code, index) => (
                          <List.Item style={{ padding: '4px 0' }}>
                            <Text code>{index + 1}. {code}</Text>
                          </List.Item>
                        )}
                      />
                    ) : (
                      <div style={{ textAlign: 'center', padding: '20px' }}>
                        <Text type="secondary">备用恢复码已隐藏</Text>
                      </div>
                    )}
                  </div>

                  <Space style={{ marginTop: '16px', width: '100%', justifyContent: 'space-between' }}>
                    <Button
                      icon={showBackupCodes ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                      onClick={() => setShowBackupCodes(!showBackupCodes)}
                    >
                      {showBackupCodes ? '隐藏' : '显示'}备用码
                    </Button>

                    <Space>
                      <Button
                        icon={<CopyOutlined />}
                        onClick={() => mfaData && copyToClipboard(
                          mfaData.backup_codes.join('\n'),
                          '备用恢复码'
                        )}
                        disabled={!showBackupCodes}
                      >
                        复制
                      </Button>
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={downloadBackupCodes}
                        type="primary"
                      >
                        下载
                      </Button>
                    </Space>
                  </Space>
                </div>
              </Col>
            </Row>

            <Divider />

            <div style={{ textAlign: 'center' }}>
              <Space>
                <Button onClick={() => setCurrentStep(0)}>
                  上一步
                </Button>
                <Button
                  type="primary"
                  onClick={() => setCurrentStep(2)}
                  icon={<MobileOutlined />}
                >
                  下一步：验证设置
                </Button>
              </Space>
            </div>
          </Card>
        );

      case 2:
        return (
          <Card className="setup-card">
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <KeyOutlined style={{ fontSize: '64px', color: '#52c41a', marginBottom: '24px' }} />
              <Title level={3}>验证MFA设置</Title>
              <Paragraph style={{ fontSize: '16px', color: '#666', maxWidth: '400px', margin: '0 auto 32px' }}>
                请打开您的认证应用，输入显示的6位数字验证码
              </Paragraph>

              <div style={{ maxWidth: '300px', margin: '0 auto 32px' }}>
                <Input
                  placeholder="000000"
                  value={verificationCode}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                    setVerificationCode(value);
                  }}
                  maxLength={6}
                  size="large"
                  style={{
                    textAlign: 'center',
                    fontSize: '24px',
                    letterSpacing: '8px',
                    fontFamily: 'monospace'
                  }}
                />
              </div>

              <Space size="large">
                <Button
                  size="large"
                  onClick={() => setCurrentStep(1)}
                >
                  上一步
                </Button>
                <Button
                  type="primary"
                  size="large"
                  onClick={handleVerifyAndEnable}
                  loading={loading}
                  disabled={verificationCode.length !== 6}
                  icon={<CheckCircleOutlined />}
                >
                  验证并启用MFA
                </Button>
              </Space>

              <div style={{ marginTop: '24px' }}>
                <Text type="secondary" style={{ fontSize: '14px' }}>
                  如果无法使用认证应用，可以使用之前保存的备用恢复码
                </Text>
              </div>
            </div>
          </Card>
        );

      case 3:
        return (
          <Card className="setup-card">
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <CheckCircleOutlined style={{ fontSize: '64px', color: '#52c41a', marginBottom: '24px' }} />
              <Title level={3}>MFA启用成功！</Title>
              <Paragraph style={{ fontSize: '16px', color: '#666', maxWidth: '400px', margin: '0 auto 32px' }}>
                您的账户已启用多因素认证保护。下次登录时需要提供认证应用中的验证码。
              </Paragraph>

              <Alert
                message="设置完成"
                description={
                  <div>
                    <p>✅ 多因素认证已启用</p>
                    <p>✅ 备用恢复码已生成</p>
                    <p>✅ 账户安全性已大幅提升</p>
                  </div>
                }
                type="success"
                showIcon
                style={{ marginBottom: '32px', textAlign: 'left' }}
              />

              <Button
                type="primary"
                size="large"
                onClick={() => navigate('/user-center/security/mfa/manage')}
              >
                管理MFA设置
              </Button>
            </div>
          </Card>
        );

      default:
        return null;
    }
  };

  return (
    <div className="mfa-setup-page" style={{ maxWidth: '800px', margin: '0 auto', padding: '24px' }}>
      <Card>
        <div style={{ marginBottom: '32px' }}>
          <Title level={2} style={{ textAlign: 'center', marginBottom: '8px' }}>
            设置多因素认证
          </Title>
          <Text type="secondary" style={{ display: 'block', textAlign: 'center' }}>
            为您的QuantMind账户添加额外的安全保护
          </Text>
        </div>

        <Steps current={currentStep} style={{ marginBottom: '32px' }}>
          {steps.map((step, index) => (
            <Step
              key={index}
              title={step.title}
              description={step.description}
              icon={step.icon}
            />
          ))}
        </Steps>

        <Spin spinning={loading && currentStep === 0}>
          {renderStepContent()}
        </Spin>
      </Card>
    </div>
  );
};

export default MFASetupPage;
