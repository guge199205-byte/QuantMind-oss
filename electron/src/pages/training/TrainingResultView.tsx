import React from 'react';
import { Card, Divider, Alert, Descriptions, Tag, Space, Typography, Empty, Button } from 'antd';
import { BarChart, MonitorPlay } from 'lucide-react';
import { 
  BarChart as ReBarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer, 
  ReferenceLine, 
  Cell 
} from 'recharts';
import dayjs from 'dayjs';
import { clsx } from 'clsx';
import { 
  TrainingResult, 
  TrainingRequestPayload,
  getObjectiveMetricDescription,
  getTargetModeDescription,
} from './trainingUtils';

const { Text } = Typography;

interface TrainingResultViewProps {
  result: TrainingResult | null;
  resultError: string;
  settingDefaultModel: boolean;
  onSetDefaultModel: () => void;
  trainingStatus: string;
}

const MetricCard: React.FC<{
  label: string;
  value: string;
  hint?: string;
  centered?: boolean;
  valueClassName?: string;
  hintClassName?: string;
}> = ({ label, value, hint, centered = false, valueClassName, hintClassName }) => (
  <div className={clsx('rounded-2xl border border-slate-200 bg-white p-4 shadow-sm', centered && 'text-center')}>
    <div className={clsx('text-[10px] font-black uppercase tracking-[0.18em] text-slate-400', centered && 'text-center')}>{label}</div>
    <div className={clsx('mt-2 text-lg font-semibold text-slate-900', centered && 'text-center', valueClassName)}>{value}</div>
    {hint ? <div className={clsx('mt-1 text-xs text-slate-500', centered && 'text-center', hintClassName)}>{hint}</div> : null}
  </div>
);

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

const renderMetaLabel = (zh: string, en: string): React.ReactNode => (
  <div className="flex flex-col items-start text-left leading-tight">
    <span className="text-slate-700">{zh}</span>
    <span className="mt-1 text-xs font-normal text-slate-500">{en}</span>
  </div>
);

export const TrainingResultView: React.FC<TrainingResultViewProps> = ({
  result,
  resultError,
  settingDefaultModel,
  onSetDefaultModel,
  trainingStatus,
}) => {
  if (!result && !resultError) {
    return (
      <Card className="rounded-3xl border-slate-200 shadow-sm" styles={{ body: { padding: 20 } }}>
         <SectionHeader
          title="第五步：结果入库"
          desc="展示训练完成后会进入模型管理页的元数据与产物预览。"
          icon={<BarChart size={18} className="text-indigo-500" />}
        />
        <Divider className="my-4" />
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="先执行训练，再查看结果摘要" />
      </Card>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <Card className="rounded-3xl border-slate-200 shadow-sm" styles={{ body: { padding: 20 } }}>
        <SectionHeader
          title="第五步：结果入库"
          desc="展示训练完成后会进入模型管理页的元数据与产物预览。"
          icon={<BarChart size={18} className="text-indigo-500" />}
        />
        <Divider className="my-4" />
        {resultError ? (
          <Alert type="error" showIcon className="mb-4 rounded-2xl" message="训练结果异常" description={resultError} />
        ) : null}
        {result ? (
          <div className="space-y-4">
            <Alert
              type="success"
              showIcon
              message={result.summary.status}
              description={result.summary.notes}
              className="rounded-2xl border-emerald-100 bg-emerald-50/70"
            />

            <Card className="rounded-2xl border-slate-200" size="small" title="模型注册与同步状态">
              <div className="flex flex-wrap items-center gap-3">
                <Tag
                  className={clsx(
                    'm-0 rounded-full border-0 px-3 py-1',
                    result.modelRegistration?.status === 'ready'
                      ? 'bg-emerald-50 text-emerald-600'
                      : result.modelRegistration?.status === 'failed'
                        ? 'bg-rose-50 text-rose-600'
                        : 'bg-amber-50 text-amber-600',
                  )}
                >
                  {result.modelRegistration?.status || 'unknown'}
                </Tag>
                <Text className="text-xs text-slate-600">
                  model_id: {result.modelRegistration?.modelId || result.modelId}
                </Text>
                <Button
                  size="small"
                  type="primary"
                  className="rounded-xl bg-blue-600"
                  loading={settingDefaultModel}
                  disabled={result.modelRegistration?.status !== 'ready'}
                  onClick={onSetDefaultModel}
                >
                  设为默认模型
                </Button>
              </div>
            </Card>

            <div className="grid gap-3 md:grid-cols-2">
              <MetricCard
                label="模型标识"
                value={result.modelId}
                hint={result.modelName}
                centered
                valueClassName="text-sm leading-tight break-all"
                hintClassName="text-[10px] leading-tight break-all"
              />
              <MetricCard
                label="T+N"
                value={`T+${result.metadata.target_horizon_days}`}
                hint={result.metadata.target_mode === 'classification' ? '分类目标' : '回归目标'}
                centered
              />
              <MetricCard
                label="提交特征数"
                value={`${result.metadata.requested_feature_count}`}
                hint={`${result.request.selectedFeatures.length} 个提交维度`}
                centered
              />
              <MetricCard
                label="实际入模特征数"
                value={`${result.metadata.feature_count}`}
                hint={result.metadata.feature_categories.join(' / ') || '—'}
                centered
              />
            </div>
            
            <Card className="rounded-2xl border-slate-200" size="small" title="模型元数据预览">
              <Descriptions size="small" bordered column={1}>
                <Descriptions.Item label={renderMetaLabel('展示名称', 'display_name')}>
                  <Text code className="text-[11px] break-all">{result.metadata.display_name}</Text>
                </Descriptions.Item>
                <Descriptions.Item label={renderMetaLabel('预测类型', 'target_mode')}>
                  {getTargetModeDescription(result.metadata.target_mode)}
                </Descriptions.Item>
                <Descriptions.Item label={renderMetaLabel('标签公式', 'label_formula')}>
                  <Text code className="text-[11px] break-all">{result.metadata.label_formula}</Text>
                </Descriptions.Item>
                <Descriptions.Item label={renderMetaLabel('时间窗口', 'training_window')}>
                  <Text code className="text-[11px] break-all">{result.metadata.training_window}</Text>
                </Descriptions.Item>
                <Descriptions.Item label={renderMetaLabel('目标函数', 'objective_metric')}>
                  {getObjectiveMetricDescription(result.metadata.objective, result.metadata.metric)}
                </Descriptions.Item>
              </Descriptions>
            </Card>

            <Card className="rounded-2xl border-slate-200" size="small" title="建议落盘文件">
              <div className="flex flex-wrap gap-2">
                {result.artifacts.map((artifact) => (
                  <Tag key={artifact} className="m-0 rounded-full border-0 bg-indigo-50 px-3 py-1 text-indigo-600">
                    {artifact}
                  </Tag>
                ))}
              </div>
            </Card>
          </div>
        ) : null}
      </Card>

      <Card className="rounded-3xl border-slate-200 shadow-sm" styles={{ body: { padding: 20 } }}>
        <SectionHeader
          title="结果摘要"
          desc="给模型管理页与后续回放使用的最小信息集合。"
          icon={<MonitorPlay size={18} className="text-indigo-500" />}
        />
        <Divider className="my-4" />
        {result ? (
          <div className="space-y-4">
            <MetricCard label="结果状态" value={trainingStatus === 'completed' ? '已生成' : '等待完成'} hint={result.completedAt ? dayjs(result.completedAt).format('YYYY-MM-DD HH:mm:ss') : ''} />
            
            {result.metrics && (
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">IC 评估图表</div>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <ReBarChart
                    data={[
                      { name: '训练集', IC: result.metrics.train.ic, RankIC: result.metrics.train.rank_ic },
                      { name: '验证集', IC: result.metrics.val.ic, RankIC: result.metrics.val.rank_ic },
                      { name: '测试集', IC: result.metrics.test.ic, RankIC: result.metrics.test.rank_ic },
                    ]}
                    barCategoryGap="30%"
                    margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => v.toFixed(2)} />
                    <Tooltip contentStyle={{ borderRadius: 12, fontSize: 11 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <ReferenceLine y={0.05} stroke="#f59e0b" strokeDasharray="5 3" />
                    <ReferenceLine y={0.10} stroke="#10b981" strokeDasharray="5 3" />
                    <Bar dataKey="IC" fill="#6366f1" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="RankIC" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                  </ReBarChart>
                </ResponsiveContainer>
                
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {(['train', 'val', 'test'] as const).map((split, i) => {
                    const labels = ['训练集', '验证集', '测试集'];
                    const seg = result.metrics![split];
                    const icVal = seg.ic;
                    const color = icVal >= 0.10 ? 'text-emerald-600' : icVal >= 0.05 ? 'text-amber-600' : 'text-rose-500';
                    return (
                      <div key={split} className="rounded-xl bg-slate-50 px-3 py-2 text-center">
                        <div className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">{labels[i]}</div>
                        <div className={`mt-0.5 text-sm font-bold ${color}`}>{icVal.toFixed(4)}</div>
                        <div className="text-[9px] text-slate-400">RankIC {seg.rank_ic.toFixed(4)}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">后续动作</div>
              <div className="mt-2 text-sm text-slate-700">
                1. 将 metadata.json 写入模型目录<br/>
                2. 在模型管理页展示 T+N / label_formula<br/>
                3. 将相同口径带入回测中心复用
              </div>
            </div>
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="训练完成后，这里会展示元数据摘要" />
        )}
      </Card>
    </div>
  );
};
