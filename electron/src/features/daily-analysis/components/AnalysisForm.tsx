import React from 'react';
import { Form, Select, Switch, Button, Space } from 'antd';
import { ThunderboltOutlined, LineChartOutlined } from '@ant-design/icons';

interface AnalysisFormProps {
  onAnalyze: (values: any) => void;
  onMarketReview: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export const AnalysisForm: React.FC<AnalysisFormProps> = ({
  onAnalyze,
  onMarketReview,
  loading,
  disabled,
}) => {
  const [form] = Form.useForm();

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      onAnalyze({
        report_type: values.report_type,
        force_refresh: values.force_refresh,
        notify: values.notify,
      });
    });
  };

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={{
        report_type: 'detailed',
        force_refresh: false,
        notify: true,
      }}
      size="small"
    >
      <Form.Item label="报告类型" name="report_type">
        <Select
          options={[
            { value: 'detailed', label: '详细分析' },
            { value: 'brief', label: '简要分析' },
            { value: 'technical', label: '技术分析' },
            { value: 'fundamental', label: '基本面分析' },
          ]}
        />
      </Form.Item>

      <Form.Item label="强制刷新" name="force_refresh" valuePropName="checked">
        <Switch size="small" />
      </Form.Item>

      <Form.Item label="发送通知" name="notify" valuePropName="checked">
        <Switch size="small" />
      </Form.Item>

      <Form.Item>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleSubmit}
            loading={loading}
            disabled={disabled}
            block
            size="large"
          >
            开始分析
          </Button>
          <Button
            icon={<LineChartOutlined />}
            onClick={onMarketReview}
            disabled={loading}
            block
          >
            大盘复盘
          </Button>
        </Space>
      </Form.Item>
    </Form>
  );
};
