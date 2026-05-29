/**
 * 管理员策略模板管理组件
 * 支持列出、新建、编辑、删除系统内置策略模板
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
    Button,
    Table,
    Tag,
    Space,
    Modal,
    Form,
    Input,
    Select,
    Popconfirm,
    message,
    Tooltip,
    Empty,
    Divider,
    Spin,
    Typography,
} from 'antd';
import {
    PlusOutlined,
    EditOutlined,
    DeleteOutlined,
    ReloadOutlined,
    CodeOutlined,
    MinusCircleOutlined,
} from '@ant-design/icons';
import Editor from '@monaco-editor/react';
import type { ColumnsType } from 'antd/es/table';
import { adminService } from '../services/adminService';
import { StrategyTemplateAdmin, StrategyTemplateUpsertRequest, StrategyTemplateParam } from '../types';

const { Text } = Typography;

const CATEGORY_OPTIONS = [
    { label: '基础策略', value: 'basic' },
    { label: '高级策略', value: 'advanced' },
    { label: '风控策略', value: 'risk_control' },
];

const DIFFICULTY_OPTIONS = [
    { label: '入门', value: 'beginner' },
    { label: '中级', value: 'intermediate' },
    { label: '高级', value: 'advanced' },
];

const categoryColor: Record<string, string> = {
    basic: 'blue',
    advanced: 'purple',
    risk_control: 'orange',
};

const difficultyColor: Record<string, string> = {
    beginner: 'green',
    intermediate: 'gold',
    advanced: 'red',
};

const categoryLabel: Record<string, string> = {
    basic: '基础',
    advanced: '高级',
    risk_control: '风控',
};

const difficultyLabel: Record<string, string> = {
    beginner: '入门',
    intermediate: '中级',
    advanced: '高级',
};

const DEFAULT_CODE = `"""
策略名称 (Strategy Name)
策略说明...
"""

STRATEGY_CONFIG = {
    "class": "RedisTopkStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "n_drop": 10,
    }
}
`;

export const AdminStrategyTemplates: React.FC = () => {
    const [templates, setTemplates] = useState<StrategyTemplateAdmin[]>([]);
    const [loading, setLoading] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [editingTemplate, setEditingTemplate] = useState<StrategyTemplateAdmin | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [code, setCode] = useState(DEFAULT_CODE);
    const [params, setParams] = useState<StrategyTemplateParam[]>([]);
    const [filterCategory, setFilterCategory] = useState<string>('all');
    const [form] = Form.useForm();

    const fetchTemplates = useCallback(async () => {
        setLoading(true);
        try {
            const res = await adminService.listStrategyTemplates();
            setTemplates(res.templates || []);
        } catch (err: any) {
            message.error(`加载模板失败: ${err.message}`);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (modalOpen) {
            if (editingTemplate) {
                form.setFieldsValue({
                    id: editingTemplate.id,
                    name: editingTemplate.name,
                    description: editingTemplate.description,
                    category: editingTemplate.category,
                    difficulty: editingTemplate.difficulty,
                });
            } else {
                form.resetFields();
            }
        }
    }, [modalOpen, editingTemplate, form]);

    useEffect(() => {
        fetchTemplates();
    }, [fetchTemplates]);

    const openCreate = () => {
        setEditingTemplate(null);
        setCode(DEFAULT_CODE);
        setParams([]);
        setModalOpen(true);
    };

    const openEdit = (tpl: StrategyTemplateAdmin) => {
        setEditingTemplate(tpl);
        setCode(tpl.code);
        setParams(tpl.params || []);
        setModalOpen(true);
    };

    const handleDelete = async (id: string) => {
        try {
            await adminService.deleteStrategyTemplate(id);
            message.success('模板已删除');
            fetchTemplates();
        } catch (err: any) {
            message.error(`删除失败: ${err.message}`);
        }
    };

    const handleSubmit = async () => {
        try {
            const values = await form.validateFields();
            setSubmitting(true);

            const payload: StrategyTemplateUpsertRequest = {
                ...values,
                code,
                params,
                execution_defaults: editingTemplate?.execution_defaults || {},
                live_defaults: editingTemplate?.live_defaults || {},
                live_config_tips: editingTemplate?.live_config_tips || [],
            };

            if (editingTemplate) {
                await adminService.updateStrategyTemplate(editingTemplate.id, payload);
                message.success(`模板「${values.name}」已更新`);
            } else {
                await adminService.createStrategyTemplate(payload);
                message.success(`模板「${values.name}」已创建`);
            }

            setModalOpen(false);
            fetchTemplates();
        } catch (err: any) {
            if (err?.errorFields) return; // 表单校验错误
            message.error(`保存失败: ${err.message}`);
        } finally {
            setSubmitting(false);
        }
    };

    // 参数列表操作
    const addParam = () => {
        setParams([...params, { name: '', description: '', default: 0 }]);
    };

    const removeParam = (idx: number) => {
        setParams(params.filter((_, i) => i !== idx));
    };

    const updateParam = (idx: number, field: keyof StrategyTemplateParam, value: any) => {
        setParams(params.map((p, i) => (i === idx ? { ...p, [field]: value } : p)));
    };

    const filteredTemplates =
        filterCategory === 'all'
            ? templates
            : templates.filter((t) => t.category === filterCategory);

    const columns: ColumnsType<StrategyTemplateAdmin> = [
        {
            title: '模板名称',
            dataIndex: 'name',
            key: 'name',
            render: (name, record) => (
                <div>
                    <Text strong>{name}</Text>
                    <div>
                        <Text type="secondary" className="text-xs">{record.id}</Text>
                    </div>
                </div>
            ),
        },
        {
            title: '分类',
            dataIndex: 'category',
            key: 'category',
            width: 90,
            render: (v) => (
                <Tag color={categoryColor[v]}>{categoryLabel[v] || v}</Tag>
            ),
        },
        {
            title: '难度',
            dataIndex: 'difficulty',
            key: 'difficulty',
            width: 80,
            render: (v) => (
                <Tag color={difficultyColor[v]}>{difficultyLabel[v] || v}</Tag>
            ),
        },
        {
            title: '描述',
            dataIndex: 'description',
            key: 'description',
            ellipsis: true,
            render: (v) => (
                <Tooltip title={v}>
                    <span className="text-gray-600 text-sm">{v}</span>
                </Tooltip>
            ),
        },
        {
            title: '参数数量',
            dataIndex: 'params',
            key: 'params',
            width: 90,
            render: (params) => (
                <Tag icon={<CodeOutlined />}>{params?.length || 0} 个</Tag>
            ),
        },
        {
            title: '操作',
            key: 'actions',
            width: 120,
            render: (_, record) => (
                <Space>
                    <Button
                        type="link"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => openEdit(record)}
                    >
                        编辑
                    </Button>
                    <Popconfirm
                        title="确认删除"
                        description={`删除后将无法恢复，确认删除「${record.name}」？`}
                        onConfirm={() => handleDelete(record.id)}
                        okText="删除"
                        okButtonProps={{ danger: true }}
                        cancelText="取消"
                    >
                        <Button
                            type="link"
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                        >
                            删除
                        </Button>
                    </Popconfirm>
                </Space>
            ),
        },
    ];

    return (
        <div className="p-4 bg-slate-50/30 min-h-full">
            {/* 页头 */}
            <div className="flex items-center justify-between mb-3">
                <div>
                    <h2 className="text-xl font-bold text-slate-900 mb-1">策略模板管理</h2>
                    <p className="text-sm text-slate-500">
                        管理系统内置策略模板，用户可通过"同步模板"将其同步到个人中心。
                    </p>
                </div>
                <Space>
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={fetchTemplates}
                        loading={loading}
                    >
                        刷新
                    </Button>
                    <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={openCreate}
                    >
                        新建模板
                    </Button>
                </Space>
            </div>

            {/* 分类过滤 */}
            <div className="flex gap-2 mb-2">
                {[
                    { key: 'all', label: `全部 (${templates.length})` },
                    { key: 'basic', label: `基础 (${templates.filter((t) => t.category === 'basic').length})` },
                    { key: 'advanced', label: `高级 (${templates.filter((t) => t.category === 'advanced').length})` },
                    { key: 'risk_control', label: `风控 (${templates.filter((t) => t.category === 'risk_control').length})` },
                ].map(({ key, label }) => (
                    <button
                        key={key}
                        onClick={() => setFilterCategory(key)}
                        className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors border ${
                            filterCategory === key
                                ? 'bg-blue-600 text-white border-blue-600'
                                : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:text-blue-600'
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* 模板表格 */}
            <Table
                columns={columns}
                dataSource={filteredTemplates}
                rowKey="id"
                loading={loading}
                locale={{ emptyText: <Empty description="暂无模板" /> }}
                pagination={{ pageSize: 10, showSizeChanger: true }}
                className="rounded-xl border border-slate-100 overflow-hidden"
            />

            {/* 新建/编辑弹窗 */}
            <Modal
                title={editingTemplate ? `编辑模板：${editingTemplate.name}` : '新建策略模板'}
                open={modalOpen}
                onCancel={() => setModalOpen(false)}
                onOk={handleSubmit}
                okText={editingTemplate ? '保存更新' : '创建模板'}
                cancelText="取消"
                confirmLoading={submitting}
                width={860}
                centered
                destroyOnHidden
                styles={{ body: { maxHeight: 'calc(100vh - 200px)', overflowY: 'auto', paddingBottom: 80 } }}
            >
                <Form form={form} layout="vertical" size="small" className="mt-2">
                    {/* 基本信息 */}
                    <div className="grid grid-cols-2 gap-4">
                        <Form.Item
                            name="name"
                            label="模板名称"
                            rules={[{ required: true, message: '请输入模板名称' }]}
                        >
                            <Input placeholder="例如：动量反转策略" />
                        </Form.Item>

                        {!editingTemplate && (
                            <Form.Item
                                name="id"
                                label={
                                    <span>
                                        模板 ID&nbsp;
                                        <Text type="secondary" className="text-xs font-normal">
                                            (可选，仅小写字母/数字/下划线)
                                        </Text>
                                    </span>
                                }
                                rules={[
                                    {
                                        pattern: /^[a-z0-9_]{0,64}$/,
                                        message: '只允许小写字母、数字和下划线',
                                    },
                                ]}
                            >
                                <Input placeholder="留空则自动生成" />
                            </Form.Item>
                        )}
                    </div>

                    <Form.Item
                        name="description"
                        label="策略描述"
                        rules={[{ required: true, message: '请输入策略描述' }]}
                        className="mb-3"
                    >
                        <Input.TextArea rows={2} placeholder="简要描述策略的核心逻辑和适用场景..." />
                    </Form.Item>

                    <div className="grid grid-cols-2 gap-4">
                        <Form.Item
                            name="category"
                            label="策略分类"
                            rules={[{ required: true, message: '请选择分类' }]}
                        >
                            <Select options={CATEGORY_OPTIONS} placeholder="选择分类" />
                        </Form.Item>
                        <Form.Item
                            name="difficulty"
                            label="难度级别"
                            rules={[{ required: true, message: '请选择难度' }]}
                        >
                            <Select options={DIFFICULTY_OPTIONS} placeholder="选择难度" />
                        </Form.Item>
                    </div>

                    <Divider orientation="left" plain className="text-xs text-slate-400 my-2">
                        可调参数定义
                    </Divider>

                    {/* 参数列表 */}
                    <div className="space-y-1 mb-2">
                        {params.map((param, idx) => (
                            <div key={idx} className="flex gap-2 items-center p-1.5 px-3 bg-slate-50 rounded-lg">
                                <Input
                                    size="small"
                                    placeholder="参数名"
                                    value={param.name}
                                    onChange={(e) => updateParam(idx, 'name', e.target.value)}
                                    className="w-28"
                                />
                                <Input
                                    size="small"
                                    placeholder="说明"
                                    value={param.description}
                                    onChange={(e) => updateParam(idx, 'description', e.target.value)}
                                    className="flex-1"
                                />
                                <Input
                                    size="small"
                                    placeholder="默认值"
                                    value={String(param.default)}
                                    onChange={(e) => updateParam(idx, 'default', e.target.value)}
                                    className="w-20"
                                />
                                <Input
                                    size="small"
                                    placeholder="最小值"
                                    type="number"
                                    value={param.min ?? ''}
                                    onChange={(e) => updateParam(idx, 'min', e.target.value === '' ? undefined : Number(e.target.value))}
                                    className="w-20"
                                />
                                <Input
                                    size="small"
                                    placeholder="最大值"
                                    type="number"
                                    value={param.max ?? ''}
                                    onChange={(e) => updateParam(idx, 'max', e.target.value === '' ? undefined : Number(e.target.value))}
                                    className="w-20"
                                />
                                <Button
                                    type="text"
                                    size="small"
                                    danger
                                    icon={<MinusCircleOutlined />}
                                    onClick={() => removeParam(idx)}
                                />
                            </div>
                        ))}
                        <Button
                            type="dashed"
                            size="small"
                            icon={<PlusOutlined />}
                            onClick={addParam}
                            block
                        >
                            添加参数
                        </Button>
                    </div>

                    <Divider orientation="left" plain className="text-xs text-slate-400 my-2">
                        策略代码（Python）
                    </Divider>

                    {/* Monaco 代码编辑器 */}
                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                        <Editor
                            height="280px"
                            language="python"
                            value={code}
                            onChange={(v) => setCode(v || '')}
                            theme="vs-light"
                            options={{
                                minimap: { enabled: false },
                                fontSize: 13,
                                lineNumbers: 'on',
                                scrollBeyondLastLine: false,
                                wordWrap: 'on',
                                tabSize: 4,
                            }}
                        />
                    </div>
                    <Text type="secondary" className="text-xs mt-1 block">
                        代码将保存为 <code>{editingTemplate?.id || 'template_id'}.py</code>，最大 200KB
                    </Text>
                </Form>
            </Modal>
        </div>
    );
};
