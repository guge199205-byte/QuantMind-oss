/**
 * MFA验证页面 - 登录时的二次验证
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Alert,
  Typography,
  Row,
  Col,
  Modal,
  message,
  Spin,
  Space,
  Divider,
  Tooltip,
} from 'antd';
import {
  MobileOutlined,
  KeyOutlined,
  SafetyCertificateOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { mfaService } from '../services/mfaService';
import { authService } from '../services/authService';
import { useAppDispatch } from '../../../store';
import { setCredentials, setUser } from '../store/authSlice';

const { Title, Text, Paragraph } = Typography;

interface MFALoginRequest {
  verification_code: string;
  temp_token: string;
}

const MFAVerificationPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const [tempToken, setTempToken] = useState('');
  const [userInfo, setUserInfo] = useState<any>(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [showBackupHelp, setShowBackupHelp] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(600); // 10分钟
  const [form] = Form.useForm();

  useEffect(() => {
    // 从URL参数或localStorage获取临时token和用户信息
    const token = searchParams.get('temp_token');
    const userStr = searchParams.get('user') || localStorage.getItem('temp_user_info');

    if (!token) {
      message.error('缺少验证信息，请重新登录');
      navigate('/auth/login');
      return;
    }

    setTempToken(token);

    if (userStr) {
      try {
        const user = JSON.parse(decodeURIComponent(userStr));
        setUserInfo(user);
      } catch (error) {
        console.error('解析用户信息失败:', error);
      }
    }

    // 设置倒计时
    const timer = setInterval(() => {
      (setTimeRemaining as any)(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          message.error('验证时间已过期，请重新登录');
          navigate('/auth/login');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [searchParams, navigate]);

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  const handleVerify = async (values: any) => {
    if (!tempToken) {
      message.error('验证令牌已失效，请重新登录');
      navigate('/auth/login');
      return;
    }

    setLoading(true);
    try {
      const requestData: MFALoginRequest = {
        verification_code: values.verification_code,
        temp_token: tempToken,
      };

      const response = await mfaService.verifyMFALogin(requestData);

      if (response.data.success) {
        const { access_token, refresh_token, user } = response.data.data;

        // 更新Redux状态
        dispatch(setCredentials({
          accessToken: access_token,
          refreshToken: refresh_token,
        }));
        dispatch(setUser(user));

        // 清除临时数据
        localStorage.removeItem('temp_user_info');

        message.success('登录成功！');
        navigate('/user-center');
      } else {
        message.error(response.data.message || '验证失败');
      }
    } catch (error: any) {
      console.error('MFA验证失败:', error);
      if (error.response?.status === 401) {
        message.error('验证令牌已过期，请重新登录');
        navigate('/auth/login');
      } else {
        message.error(error.response?.data?.message || '验证失败，请重试');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUseBackupCode = () => {
    Modal.confirm({
      title: '使用备用恢复码',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <Paragraph>
            备用恢复码是在您无法使用认证应用时的最后手段。
            每个备用码只能使用一次。
          </Paragraph>
          <Alert
            message="注意"
            description="使用备用码后，建议立即重新生成新的备用码"
            type="warning"
            showIcon
            style={{ marginTop: '16px' }}
          />
        </div>
      ),
      okText: '我知道了',
      cancelText: '取消',
      onOk() {
        form.setFieldsValue({ verification_code: '' });
        form.getFieldInstance('verification_code')?.focus();
      },
    });
  };

  const handleResendCode = () => {
    message.info('验证码由认证应用生成，无法重新发送。请打开您的认证应用查看最新验证码。');
  };

  const handleBackToLogin = () => {
    localStorage.removeItem('temp_user_info');
    navigate('/auth/login');
  };

  return (
    <div className="mfa-verification-page" style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <Card
        className="auth-rounded-card"
        style={{
          width: '100%',
          maxWidth: '480px',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
        }}
        styles={{ body: { padding: '40px', borderRadius: 'inherit', overflow: 'hidden' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <SafetyCertificateOutlined style={{
            fontSize: '48px',
            color: '#1890ff',
            marginBottom: '16px'
          }} />
          <Title level={3} style={{ marginBottom: '8px' }}>
            多因素认证验证
          </Title>
          <Text type="secondary">
            请输入您的认证应用中显示的验证码
          </Text>
        </div>

        {userInfo && (
          <Alert
            message={`正在为 ${userInfo.email} 进行验证`}
            type="info"
            showIcon
            style={{ marginBottom: '24px' }}
          />
        )}

        <div style={{
          background: '#fff3cd',
          border: '1px solid #ffeaa7',
          borderRadius: '6px',
          padding: '12px',
          marginBottom: '24px',
          textAlign: 'center'
        }}>
          <Text style={{ color: '#856404' }}>
            <ReloadOutlined style={{ marginRight: '8px' }} />
            验证将在 {formatTime(timeRemaining)} 后过期
          </Text>
        </div>

        <Form
          form={form}
          onFinish={handleVerify}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="verification_code"
            label="验证码"
            rules={[
              { required: true, message: '请输入6位验证码' },
              {
                pattern: /^\d{6}$/,
                message: '验证码必须是6位数字'
              }
            ]}
          >
            <Input
              placeholder="000000"
              maxLength={6}
              style={{
                textAlign: 'center',
                fontSize: '20px',
                letterSpacing: '6px',
                fontFamily: 'monospace',
              }}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '');
                form.setFieldsValue({ verification_code: value });
              }}
              suffix={
                <Tooltip title="请打开Google Authenticator等认证应用，查看6位数字验证码">
                  <QuestionCircleOutlined style={{ color: '#999' }} />
                </Tooltip>
              }
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: '16px' }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
              icon={<MobileOutlined />}
            >
              验证并登录
            </Button>
          </Form.Item>
        </Form>

        <Divider style={{ margin: '24px 0' }} />

        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Button
            type="link"
            onClick={handleUseBackupCode}
            block
            icon={<KeyOutlined />}
          >
            无法使用认证应用？使用备用恢复码
          </Button>

          <Button
            type="link"
            onClick={handleResendCode}
            block
            icon={<ReloadOutlined />}
          >
            验证码不正确？
          </Button>

          <Button
            type="link"
            onClick={handleBackToLogin}
            block
            style={{ color: '#999' }}
          >
            返回登录页面
          </Button>
        </Space>

        <Alert
          message="安全提示"
          description={
            <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
              <li>验证码每30秒更新一次</li>
              <li>请确保手机时间准确</li>
              <li>备用恢复码请妥善保管</li>
            </ul>
          }
          type="info"
          showIcon
          style={{ marginTop: '24px' }}
        />
      </Card>
    </div>
  );
};

export default MFAVerificationPage;
