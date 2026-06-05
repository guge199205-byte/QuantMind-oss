/**
 * 特征字典管理（管理员）
 *
 * 编辑模型训练特征字典：分类增删改、特征增删改、启用/禁用、保存到后端 JSON 文件。
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Checkbox,
  Divider,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  DatabaseOutlined,
  FolderOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { adminService } from '../services/adminService';
import type { AdminModelFeatureCatalog, AdminModelFeatureCategory, AdminModelFeatureItem } from '../types';

const { Title, Text } = Typography;

const MARKET_OPTIONS = [
  { value: 'CN', label: 'A股', color: 'red' },
  { value: 'HK', label: '港股', color: 'blue' },
  { value: 'US', label: '美股', color: 'green' },
  { value: 'CRYPTO', label: '加密', color: 'purple' },
];

// ─── 辅助函数 ────────────────────────────────────────────────────────────────

function generateFeatureId(): string {
  return 'feat_' + Math.random().toString(36).slice(2, 10);
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────

export const AdminFeatureCatalog: React.FC = () => {
  const [catalog, setCatalog] = useState<AdminModelFeatureCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [selectedCatId, setSelectedCatId] = useState<string | null>(null);

  // 分类编辑
  const [catModalOpen, setCatModalOpen] = useState(false);
  const [editingCat, setEditingCat] = useState<AdminModelFeatureCategory | null>(null);
  const [catForm] = Form.useForm();

  // 特征编辑
  const [featModalOpen, setFeatModalOpen] = useState(false);
  const [editingFeat, setEditingFeat] = useState<AdminModelFeatureItem | null>(null);
  const [featForm] = Form.useForm();

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminService.getModelFeatureCatalog();
      setCatalog(data);
      if (!selectedCatId && data.categories?.length) {
        setSelectedCatId(data.categories[0].id);
      }
      setDirty(false);
    } catch {
      message.error('加载特征字典失败');
    } finally {
      setLoading(false);
    }
  }, [selectedCatId]);

  useEffect(() => { loadCatalog(); }, [loadCatalog]);

  const markDirty = () => setDirty(true);

  // ─── 保存 ────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!catalog) return;
    setSaving(true);
    try {
      const resp = await adminService.updateFeatureCatalog(catalog);
      message.success(`已保存 ${resp.feature_count} 个特征`);
      setDirty(false);
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  // ─── 分类 CRUD ────────────────────────────────────────────────────────────

  const openAddCategory = () => {
    setEditingCat(null);
    catForm.resetFields();
    setCatModalOpen(true);
  };

  const openEditCategory = (cat: AdminModelFeatureCategory) => {
    setEditingCat(cat);
    catForm.setFieldsValue({ id: cat.id, name: cat.name, order: cat.order });
    setCatModalOpen(true);
  };

  const handleSaveCategory = async () => {
    const values = await catForm.validateFields();
    if (!catalog) return;

    const cats = [...catalog.categories];
    if (editingCat) {
      const idx = cats.findIndex(c => c.id === editingCat.id);
      if (idx >= 0) {
        cats[idx] = { ...cats[idx], id: values.id, name: values.name, order: values.order };
      }
    } else {
      if (cats.some(c => c.id === values.id)) {
        message.error('分类 ID 已存在');
        return;
      }
      cats.push({
        id: values.id,
        name: values.name,
        order: values.order ?? cats.length,
        feature_count: 0,
        features: [],
      });
    }
    cats.sort((a, b) => (a.order || 0) - (b.order || 0));
    setCatalog({ ...catalog, categories: cats });
    setSelectedCatId(values.id);
    setCatModalOpen(false);
    markDirty();
  };

  const handleDeleteCategory = (catId: string) => {
    if (!catalog) return;
    const cats = catalog.categories.filter(c => c.id !== catId);
    setCatalog({ ...catalog, categories: cats });
    if (selectedCatId === catId) {
      setSelectedCatId(cats[0]?.id ?? null);
    }
    markDirty();
  };

  // ─── 特征 CRUD ────────────────────────────────────────────────────────────

  const selectedCat = catalog?.categories.find(c => c.id === selectedCatId) ?? null;

  const openAddFeature = () => {
    setEditingFeat(null);
    featForm.resetFields();
    featForm.setFieldsValue({ markets: MARKET_OPTIONS.map(m => m.value) });
    setFeatModalOpen(true);
  };

  const openEditFeature = (feat: AdminModelFeatureItem) => {
    setEditingFeat(feat);
    featForm.setFieldsValue({
      key: feat.key,
      feature_name: feat.feature_name,
      formula: feat.formula,
      source_table_fields: feat.source_table_fields,
      markets: feat.markets && feat.markets.length > 0 ? feat.markets : MARKET_OPTIONS.map(m => m.value),
    });
    setFeatModalOpen(true);
  };

  const handleSaveFeature = async () => {
    const values = await featForm.validateFields();
    if (!catalog || !selectedCatId) return;

    // 处理 markets：全选时设为空数组（表示适用所有市场）
    const allMarketValues = MARKET_OPTIONS.map(m => m.value);
    const markets = values.markets && values.markets.length === allMarketValues.length ? [] : (values.markets || []);

    const cats = catalog.categories.map(cat => {
      if (cat.id !== selectedCatId) return cat;
      const features = [...cat.features];
      if (editingFeat) {
        const idx = features.findIndex(f => f.key === editingFeat.key);
        if (idx >= 0) {
          features[idx] = { ...features[idx], ...values, markets };
        }
      } else {
        if (features.some(f => f.key === values.key)) {
          message.error('特征 key 已存在');
          return cat;
        }
        features.push({
          feature_id: generateFeatureId(),
          key: values.key,
          feature_name: values.feature_name,
          formula: values.formula || '',
          source_table_fields: values.source_table_fields || '',
          enabled: true,
          order_no: features.length + 1,
          markets,
        });
      }
      return { ...cat, features, feature_count: features.length };
    });
    setCatalog({ ...catalog, categories: cats });
    setFeatModalOpen(false);
    markDirty();
  };

  const handleDeleteFeature = (featureKey: string) => {
    if (!catalog || !selectedCatId) return;
    const cats = catalog.categories.map(cat => {
      if (cat.id !== selectedCatId) return cat;
      const features = cat.features.filter(f => f.key !== featureKey);
      return { ...cat, features, feature_count: features.length };
    });
    setCatalog({ ...catalog, categories: cats });
    markDirty();
  };

  const handleToggleFeature = (featureKey: string, enabled: boolean) => {
    if (!catalog || !selectedCatId) return;
    const cats = catalog.categories.map(cat => {
      if (cat.id !== selectedCatId) return cat;
      const features = cat.features.map(f =>
        f.key === featureKey ? { ...f, enabled } : f
      );
      return { ...cat, features };
    });
    setCatalog({ ...catalog, categories: cats });
    markDirty();
  };

  // ─── 表格列定义 ──────────────────────────────────────────────────────────

  const featureColumns: ColumnsType<AdminModelFeatureItem> = [
    {
      title: 'Key',
      dataIndex: 'key',
      width: 200,
      render: (key: string) => <Text code className="text-xs">{key}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'feature_name',
      ellipsis: true,
    },
    {
      title: '公式',
      dataIndex: 'formula',
      ellipsis: true,
      width: 200,
      render: (v: string) => v ? <Text type="secondary" className="text-xs font-mono">{v}</Text> : '—',
    },
    {
      title: '市场',
      dataIndex: 'markets',
      width: 180,
      render: (markets: string[] | undefined) => {
        const list = markets && markets.length > 0 ? markets : MARKET_OPTIONS.map(m => m.value);
        return (
          <Space size={2} wrap>
            {list.map(m => {
              const opt = MARKET_OPTIONS.find(o => o.value === m);
              return <Tag key={m} color={opt?.color || 'default'} className="text-[10px] m-0">{opt?.label || m}</Tag>;
            })}
          </Space>
        );
      },
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 80,
      align: 'center',
      render: (enabled: boolean, record) => (
        <Switch
          size="small"
          checked={enabled}
          onChange={(checked) => handleToggleFeature(record.key, checked)}
        />
      ),
    },
    {
      title: '操作',
      width: 100,
      align: 'center',
      render: (_: unknown, record) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditFeature(record)} />
          </Tooltip>
          <Popconfirm title="确认删除此特征？" onConfirm={() => handleDeleteFeature(record.key)}>
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ─── 渲染 ──────────────────────────────────────────────────────────────────

  if (!catalog) {
    return <Card loading={loading} className="m-8"><Empty description="加载中..." /></Card>;
  }

  const totalFeatures = catalog.categories.reduce((sum, c) => sum + c.features.length, 0);

  return (
    <div className="p-6 space-y-4">
      {/* 顶栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <DatabaseOutlined className="text-xl text-blue-500" />
          <div>
            <Title level={4} className="!m-0">特征字典管理</Title>
            <Text type="secondary" className="text-xs">
              {catalog.categories.length} 个分类 · {totalFeatures} 个特征 · 来源: {catalog.source || 'file'}
            </Text>
          </div>
        </div>
        <Space>
          {dirty && <Tag color="warning">未保存</Tag>}
          <Button icon={<ReloadOutlined />} onClick={loadCatalog} loading={loading}>刷新</Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving} disabled={!dirty}>
            保存
          </Button>
        </Space>
      </div>

      <Divider className="!my-2" />

      {/* 主体：左侧分类列表 + 右侧特征表格 */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '280px 1fr' }}>
        {/* 左侧分类列表 */}
        <Card
          size="small"
          title={<span className="text-sm font-semibold">分类列表</span>}
          extra={
            <Button type="text" size="small" icon={<PlusOutlined />} onClick={openAddCategory}>
              新增
            </Button>
          }
          className="h-fit"
          styles={{ body: { padding: 0, maxHeight: 'calc(100vh - 260px)', overflowY: 'auto' } }}
        >
          {catalog.categories.map(cat => (
            <div
              key={cat.id}
              className={`flex items-center justify-between px-4 py-3 cursor-pointer border-b border-gray-50 transition-colors ${
                selectedCatId === cat.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50'
              }`}
              onClick={() => setSelectedCatId(cat.id)}
            >
              <div className="flex items-center gap-2 min-w-0">
                <FolderOutlined className={selectedCatId === cat.id ? 'text-blue-500' : 'text-gray-400'} />
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{cat.name}</div>
                  <div className="text-xs text-gray-400">{cat.id} · {cat.features.length} 个特征</div>
                </div>
              </div>
              <Space size="small" onClick={e => e.stopPropagation()}>
                <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditCategory(cat)} />
                <Popconfirm title="确认删除此分类及所有特征？" onConfirm={() => handleDeleteCategory(cat.id)}>
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            </div>
          ))}
          {catalog.categories.length === 0 && (
            <div className="p-8 text-center text-gray-400 text-sm">暂无分类</div>
          )}
        </Card>

        {/* 右侧特征表格 */}
        <Card
          size="small"
          title={
            <span className="text-sm font-semibold">
              {selectedCat ? `${selectedCat.name} — 特征列表` : '请选择分类'}
            </span>
          }
          extra={
            selectedCat && (
              <Button type="text" size="small" icon={<PlusOutlined />} onClick={openAddFeature}>
                新增特征
              </Button>
            )
          }
        >
          {selectedCat ? (
            <Table
              dataSource={selectedCat.features}
              columns={featureColumns}
              rowKey="key"
              size="small"
              pagination={false}
              scroll={{ y: 'calc(100vh - 340px)' }}
            />
          ) : (
            <Empty description="请从左侧选择一个分类" />
          )}
        </Card>
      </div>

      {/* 分类编辑弹窗 */}
      <Modal
        title={editingCat ? '编辑分类' : '新增分类'}
        open={catModalOpen}
        onOk={handleSaveCategory}
        onCancel={() => setCatModalOpen(false)}
        destroyOnClose
      >
        <Form form={catForm} layout="vertical">
          <Form.Item name="id" label="分类 ID" rules={[{ required: true, message: '请输入分类 ID' }]}>
            <Input placeholder="例如: momentum" disabled={!!editingCat} />
          </Form.Item>
          <Form.Item name="name" label="分类名称" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="例如: 动量" />
          </Form.Item>
          <Form.Item name="order" label="排序" initialValue={0}>
            <Input type="number" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 特征编辑弹窗 */}
      <Modal
        title={editingFeat ? '编辑特征' : '新增特征'}
        open={featModalOpen}
        onOk={handleSaveFeature}
        onCancel={() => setFeatModalOpen(false)}
        destroyOnClose
      >
        <Form form={featForm} layout="vertical">
          <Form.Item name="key" label="特征 Key" rules={[{ required: true, message: '请输入特征 Key' }]}>
            <Input placeholder="例如: mom_ret_1d" disabled={!!editingFeat} />
          </Form.Item>
          <Form.Item name="feature_name" label="特征名称" rules={[{ required: true, message: '请输入特征名称' }]}>
            <Input placeholder="例如: 1日收益率动量" />
          </Form.Item>
          <Form.Item name="formula" label="公式">
            <Input placeholder="例如: (C_t/C_{t-1})-1" />
          </Form.Item>
          <Form.Item name="source_table_fields" label="数据来源">
            <Input placeholder="例如: stock_daily.ClosePrice" />
          </Form.Item>
          <Form.Item name="markets" label="适用市场" initialValue={MARKET_OPTIONS.map(m => m.value)}>
            <Checkbox.Group options={MARKET_OPTIONS.map(m => ({ label: m.label, value: m.value }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
