import React from 'react';
import { Card, Divider, Input, Button, Row, Col, InputNumber, Select, Alert, Typography } from 'antd';
import { Settings2, MonitorPlay } from 'lucide-react';
import { 
  TrainingParams, 
  TrainingContext, 
  DealPrice 
} from './trainingUtils';

interface ParameterConfigProps {
  params: TrainingParams;
  context: TrainingContext;
  onParamsChange: (params: TrainingParams) => void;
  onContextChange: (context: TrainingContext) => void;
  displayName: string;
  onDisplayNameChange: (name: string, mode: 'auto' | 'manual') => void;
  autoDisplayName: string;
}

const SectionHeader: React.FC<{ title: string; desc: string; icon?: React.ReactNode }> = ({ title, desc, icon }) => (
  <div className="flex items-start justify-between gap-4">
    <div>
      <div className="flex items-center gap-2">
        {icon}
        <Typography.Title level={4} className="!mb-0 !text-slate-900">
          {title}
        </Typography.Title>
      </div>
      <Typography.Paragraph className="!mb-0 !mt-2 !text-xs !text-slate-500 leading-relaxed">
        {desc}
      </Typography.Paragraph>
    </div>
  </div>
);

export const ParameterConfig: React.FC<ParameterConfigProps> = ({
  params,
  context,
  onParamsChange,
  onContextChange,
  displayName,
  onDisplayNameChange,
  autoDisplayName,
}) => {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <Card className="rounded-3xl border-slate-200 shadow-sm" styles={{ body: { padding: 20 } }}>
        <SectionHeader
          title="第三步：参数配置"
          desc="把模型超参与训练上下文拆开，避免配置语义混在一起。"
          icon={<Settings2 size={18} className="text-indigo-500" />}
        />
        <Divider className="my-4" />
        <div className="space-y-4">
          <Card className="rounded-2xl border-slate-200" size="small" title="模型命名">
            <div className="space-y-2">
              <div className="text-xs text-slate-500">
                display_name 用于模型管理页展示和训练结果命名，自动规则为“日期_T+N_模型维度_版本”。
              </div>
              <div className="flex gap-2">
                <Input
                  value={displayName}
                  onChange={(event) => onDisplayNameChange(event.target.value, 'manual')}
                  placeholder={autoDisplayName}
                  className="rounded-xl"
                  maxLength={128}
                />
                <Button
                  className="rounded-xl"
                  onClick={() => onDisplayNameChange(autoDisplayName, 'auto')}
                >
                  恢复自动
                </Button>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                <span>当前自动示例：{autoDisplayName}</span>
                <span>{displayName.trim().length}/128</span>
              </div>
            </div>
          </Card>

          <Card className="rounded-2xl border-slate-200" size="small" title="训练超参">
            <Row gutter={[12, 12]}>
              {[
                ['learning_rate', '学习率'],
                ['num_leaves', '叶子数'],
                ['max_depth', '最大深度'],
                ['min_data_in_leaf', '叶子最小样本'],
                ['lambda_l1', 'L1 正则'],
                ['lambda_l2', 'L2 正则'],
                ['feature_fraction', '特征采样'],
                ['bagging_fraction', '行采样'],
                ['num_boost_round', '最大迭代轮数'],
                ['early_stopping_rounds', '早停轮数'],
              ].map(([key, label]) => {
                const numberKey = key as keyof TrainingParams;
                const limits: Record<string, { min?: number; max?: number; step?: number }> = {
                  learning_rate: { min: 0.0001, max: 1, step: 0.001 },
                  num_leaves: { min: 1, max: 1024, step: 1 },
                  max_depth: { min: -1, max: 64, step: 1 },
                  min_data_in_leaf: { min: 1, max: 10000, step: 1 },
                  lambda_l1: { min: 0, max: 10, step: 0.1 },
                  lambda_l2: { min: 0, max: 10, step: 0.1 },
                  feature_fraction: { min: 0.1, max: 1, step: 0.01 },
                  bagging_fraction: { min: 0.1, max: 1, step: 0.01 },
                  num_boost_round: { min: 1, max: 10000, step: 10 },
                  early_stopping_rounds: { min: 1, max: 1000, step: 5 },
                };
                return (
                  <Col span={12} key={key}>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-500">{label}</div>
                      <InputNumber
                        value={params[numberKey] as number}
                        min={limits[key]?.min}
                        max={limits[key]?.max}
                        step={limits[key]?.step}
                        className="w-full"
                        onChange={(value) => onParamsChange({ ...params, [numberKey]: Number(value ?? params[numberKey]) })}
                      />
                    </div>
                  </Col>
                );
              })}
            </Row>
          </Card>

          <Card className="rounded-2xl border-slate-200" size="small" title="训练目标对应的目标函数">
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <div className="space-y-1">
                  <div className="text-xs text-slate-500">Objective</div>
                  <Select
                    value={params.objective}
                    className="w-full"
                    onChange={(value) => onParamsChange({ ...params, objective: value as TrainingParams['objective'] })}
                    options={[
                      { label: '回归 (regression)', value: 'regression' },
                      { label: '二分类 (binary)', value: 'binary' },
                    ]}
                  />
                </div>
              </Col>
              <Col span={12}>
                <div className="space-y-1">
                  <div className="text-xs text-slate-500">Metric</div>
                  <Select
                    value={params.metric}
                    className="w-full"
                    onChange={(value) => onParamsChange({ ...params, metric: value as TrainingParams['metric'] })}
                    options={[
                      { label: 'L2', value: 'l2' },
                      { label: 'RMSE', value: 'rmse' },
                      { label: 'MAE', value: 'mae' },
                      { label: 'AUC', value: 'auc' },
                      { label: 'Binary Logloss', value: 'binary_logloss' },
                    ]}
                  />
                </div>
              </Col>
            </Row>
          </Card>
        </div>
      </Card>

      <Card className="rounded-3xl border-slate-200 shadow-sm" styles={{ body: { padding: 20 } }}>
        <SectionHeader
          title="训练上下文"
          desc="记录训练时的资产、基准与交易成本，方便后续回放与模型管理页对齐。"
          icon={<MonitorPlay size={18} className="text-indigo-500" />}
        />
        <Divider className="my-4" />
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <div className="mb-1 text-xs text-slate-500">初始资金</div>
                <InputNumber
                  value={context.initialCapital}
                  min={1000}
                  step={10000}
                  className="w-full"
                  onChange={(value) => onContextChange({ ...context, initialCapital: Number(value ?? context.initialCapital) })}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-500">基准指数</div>
                <Select
                  value={context.benchmark}
                  className="w-full"
                  onChange={(value) => onContextChange({ ...context, benchmark: value })}
                  options={[
                    { label: '沪深300', value: 'SH000300' },
                    { label: '中证500', value: 'SH000905' },
                    { label: '中证1000', value: 'SH000852' },
                  ]}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-500">手续费率</div>
                <InputNumber
                  value={context.commissionRate}
                  min={0}
                  max={1}
                  step={0.0001}
                  className="w-full"
                  onChange={(value) => onContextChange({ ...context, commissionRate: Number(value ?? context.commissionRate) })}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-500">滑点</div>
                <InputNumber
                  value={context.slippage}
                  min={0}
                  max={1}
                  step={0.0001}
                  className="w-full"
                  onChange={(value) => onContextChange({ ...context, slippage: Number(value ?? context.slippage) })}
                />
              </div>
              <div className="md:col-span-2">
                <div className="mb-1 text-xs text-slate-500">成交价格</div>
                <Select
                  value={context.dealPrice}
                  className="w-full"
                  onChange={(value) => onContextChange({ ...context, dealPrice: value as DealPrice })}
                  options={[
                    { label: '开盘价 (open)', value: 'open' },
                    { label: '收盘价 (close)', value: 'close' },
                  ]}
                />
              </div>
            </div>
          </div>

          <Alert
            type="warning"
            showIcon
            message="口径提醒"
            description="训练上下文会写入请求预览和模型元数据，保证模型管理页、回测中心和训练页使用同一套参数口径。"
            className="rounded-2xl border-amber-100 bg-amber-50/70"
          />
        </div>
      </Card>
    </div>
  );
};
