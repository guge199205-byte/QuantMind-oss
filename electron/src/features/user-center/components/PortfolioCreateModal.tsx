/**
 * 创建投资组合对话框
 */

import React from 'react';
import { Modal, Form, Input, InputNumber, Switch, message } from 'antd';
import { SERVICE_ENDPOINTS } from '../../../config/services';
import type { PortfolioCreate } from '../types';

interface PortfolioCreateModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  userId: string;
}

const PortfolioCreateModal: React.FC<PortfolioCreateModalProps> = ({
  visible,
  onCancel,
  onSuccess,
  userId,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      // API调用
      const response = await fetch(`${SERVICE_ENDPOINTS.USER_SERVICE}/users/${userId}/portfolios`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify(values as PortfolioCreate),
      });

      if (!response.ok) {
        throw new Error('创建投资组合失败');
      }

      message.success('投资组合创建成功');
      form.resetFields();
      onSuccess();
    } catch (error: any) {
      message.error(error.message || '创建失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onCancel();
  };

  return (
    <Modal
      title="创建投资组合"
      open={visible}
      onOk={handleSubmit}
      onCancel={handleCancel}
      confirmLoading={loading}
      destroyOnHidden
      width={600}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          initial_cash: 100000,
          is_default: false,
          is_public: false,
        }}
      >
        <Form.Item
          label="组合名称"
          name="portfolio_name"
          rules={[
            { required: true, message: '请输入组合名称' },
            { max: 100, message: '名称不能超过100个字符' },
          ]}
        >
          <Input placeholder="例如：价值投资组合" />
        </Form.Item>

        <Form.Item
          label="组合描述"
          name="description"
          rules={[{ max: 500, message: '描述不能超过500个字符' }]}
        >
          <Input.TextArea
            placeholder="描述您的投资策略和目标..."
            rows={4}
            showCount
            maxLength={500}
          />
        </Form.Item>

        <Form.Item
          label="初始资金 (元)"
          name="initial_cash"
          rules={[
            { required: true, message: '请输入初始资金' },
            { type: 'number', min: 0, message: '初始资金必须大于0' },
          ]}
        >
          <InputNumber
            style={{ width: '100%' }}
            min={0}
            precision={2}
            formatter={(value) => `¥ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
            parser={(value) => value!.replace(/¥\s?|(,*)/g, '') as any}
          />
        </Form.Item>

        <Form.Item
          label="设为默认组合"
          name="is_default"
          valuePropName="checked"
          tooltip="默认组合将在首页和其他位置优先显示"
        >
          <Switch />
        </Form.Item>

        <Form.Item
          label="公开组合"
          name="is_public"
          valuePropName="checked"
          tooltip="公开组合可以被其他用户查看（个人信息仍受隐私设置保护）"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default PortfolioCreateModal;
