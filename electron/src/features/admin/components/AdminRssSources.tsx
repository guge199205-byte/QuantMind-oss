/**
 * RSS 源管理（管理员）
 *
 * 代理 Huntly 的 /api/setting/feeds/* 与 /api/setting/folder/*
 * 提供：列表 / 预览 / 新增 / 删除 / 重命名 / 移动文件夹 / 文件夹 CRUD
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
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
  EyeOutlined,
  FolderAddOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  newsService,
  type HuntlyConnector,
  type HuntlyFeedPreview,
  type HuntlyFolder,
} from '../../news/services/newsService';

const { Title, Text } = Typography;

interface SourceRow extends HuntlyConnector {
  folderId: number | null;
  folderName: string;
}

const UNGROUPED_LABEL = '未分组';

export const AdminRssSources: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [folders, setFolders] = useState<HuntlyFolder[]>([]);

  // —— 新增源 modal
  const [addOpen, setAddOpen] = useState(false);
  const [addForm] = Form.useForm();
  const [previewing, setPreviewing] = useState(false);
  const [previewData, setPreviewData] = useState<HuntlyFeedPreview | null>(null);

  // —— 编辑源 modal
  const [editOpen, setEditOpen] = useState(false);
  const [editForm] = Form.useForm();
  const [editingId, setEditingId] = useState<number | null>(null);

  // —— 文件夹管理 modal
  const [folderOpen, setFolderOpen] = useState(false);
  const [folderName, setFolderName] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await newsService.adminListFolders();
      setFolders(r.folders || []);
    } catch (e: any) {
      message.error(`加载失败: ${e?.response?.data?.detail || e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const folderOptions = useMemo(
    () => [
      { label: UNGROUPED_LABEL, value: 0 },
      ...folders
        .filter((f) => f.id != null)
        .map((f) => ({ label: f.name || `#${f.id}`, value: f.id as number })),
    ],
    [folders],
  );

  const rows: SourceRow[] = useMemo(() => {
    const out: SourceRow[] = [];
    folders.forEach((f) => {
      const folderId = f.id ?? null;
      const folderName = f.name || UNGROUPED_LABEL;
      (f.connectors || []).forEach((c) => {
        out.push({ ...c, folderId, folderName });
      });
    });
    return out;
  }, [folders]);

  const handlePreview = async () => {
    const url = addForm.getFieldValue('subscribe_url');
    if (!url) {
      message.warning('请先填写订阅地址');
      return;
    }
    setPreviewing(true);
    setPreviewData(null);
    try {
      const data = await newsService.adminPreviewFeed(url);
      setPreviewData(data);
      if (data?.title) {
        message.success(`预览成功：${data.title}`);
      }
    } catch (e: any) {
      message.error(`预览失败: ${e?.response?.data?.detail || e?.message || e}`);
    } finally {
      setPreviewing(false);
    }
  };

  const handleAddSubmit = async () => {
    const values = await addForm.validateFields();
    try {
      await newsService.adminCreateSource({
        subscribe_url: String(values.subscribe_url).trim(),
        folder_id: values.folder_id ?? null,
        name: values.name?.trim() || undefined,
      });
      message.success('订阅源已添加');
      setAddOpen(false);
      addForm.resetFields();
      setPreviewData(null);
      refresh();
    } catch (e: any) {
      message.error(`添加失败: ${e?.response?.data?.detail || e?.message || e}`);
    }
  };

  const openEdit = async (row: SourceRow) => {
    setEditingId(row.id);
    try {
      const detail = await newsService.adminGetSourceSetting(row.id);
      editForm.setFieldsValue({
        name: detail.name,
        folder_id: detail.folderId ?? 0,
        fetch_interval_minutes:
          detail.fetchIntervalMinutes ?? detail.defaultFetchIntervalMinutes,
        enabled: detail.enabled,
        crawl_full_content: !!detail.crawlFullContent,
        subscribe_url: detail.subscribeUrl,
      });
      setEditOpen(true);
    } catch (e: any) {
      message.error(`加载详情失败: ${e?.response?.data?.detail || e?.message || e}`);
    }
  };

  const handleEditSubmit = async () => {
    if (editingId == null) return;
    const values = await editForm.validateFields();
    try {
      await newsService.adminUpdateSource(editingId, {
        name: values.name?.trim(),
        folder_id: values.folder_id ?? null,
        fetch_interval_minutes: values.fetch_interval_minutes,
        enabled: values.enabled,
        crawl_full_content: values.crawl_full_content,
      });
      message.success('已保存');
      setEditOpen(false);
      refresh();
    } catch (e: any) {
      message.error(`保存失败: ${e?.response?.data?.detail || e?.message || e}`);
    }
  };

  const handleDelete = async (row: SourceRow) => {
    try {
      await newsService.adminDeleteSource(row.id);
      message.success(`已删除：${row.name}`);
      refresh();
    } catch (e: any) {
      message.error(`删除失败: ${e?.response?.data?.detail || e?.message || e}`);
    }
  };

  const handleAddFolder = async () => {
    const name = folderName.trim();
    if (!name) {
      message.warning('文件夹名不能为空');
      return;
    }
    try {
      await newsService.adminCreateFolder(name);
      message.success(`文件夹「${name}」已创建`);
      setFolderName('');
      refresh();
    } catch (e: any) {
      message.error(`创建失败: ${e?.response?.data?.detail || e?.message || e}`);
    }
  };

  const handleRenameFolder = async (folder: HuntlyFolder) => {
    const next = window.prompt('重命名文件夹', folder.name || '');
    if (!next || !next.trim() || next.trim() === folder.name) return;
    try {
      await newsService.adminRenameFolder(folder.id as number, next.trim());
      message.success('已重命名');
      refresh();
    } catch (e: any) {
      message.error(`重命名失败: ${e?.response?.data?.detail || e?.message || e}`);
    }
  };

  const handleDeleteFolder = async (folder: HuntlyFolder) => {
    try {
      await newsService.adminDeleteFolder(folder.id as number);
      message.success(`已删除文件夹：${folder.name}`);
      refresh();
    } catch (e: any) {
      message.error(`删除失败: ${e?.response?.data?.detail || e?.message || e}`);
    }
  };

  const columns: ColumnsType<SourceRow> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, row) => (
        <Space>
          {row.iconUrl ? (
            <img src={row.iconUrl} alt="" style={{ width: 16, height: 16 }} />
          ) : null}
          <Text strong>{text || '(未命名)'}</Text>
          {row.type ? <Tag color="default">{row.type}</Tag> : null}
        </Space>
      ),
    },
    {
      title: '订阅地址',
      dataIndex: 'subscribeUrl',
      key: 'subscribeUrl',
      ellipsis: true,
      render: (u) => (
        <Tooltip title={u}>
          <Text type="secondary" copyable={!!u} ellipsis>
            {u}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '所在文件夹',
      dataIndex: 'folderName',
      key: 'folderName',
      width: 160,
      render: (n) => <Tag color={n === UNGROUPED_LABEL ? 'default' : 'blue'}>{n}</Tag>,
    },
    {
      title: '未读',
      dataIndex: 'inboxCount',
      key: 'inboxCount',
      width: 80,
      align: 'right',
      render: (v) => (v ? <Tag color="orange">{v}</Tag> : <Text type="secondary">0</Text>),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_, row) => (
        <Space>
          <Tooltip title="编辑">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)} />
          </Tooltip>
          <Popconfirm
            title={`确定删除「${row.name || row.id}」吗？`}
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            onConfirm={() => handleDelete(row)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <Title level={4} style={{ margin: 0 }}>RSS 源管理</Title>
          <Text type="secondary">代理 Huntly 订阅源 CRUD — 与前台「RSS信息流」共用同一数据</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={refresh}>刷新</Button>
          <Button
            icon={<FolderAddOutlined />}
            onClick={() => setFolderOpen(true)}
          >
            管理文件夹
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              addForm.resetFields();
              setPreviewData(null);
              setAddOpen(true);
            }}
          >
            新增订阅源
          </Button>
        </Space>
      </div>

      <Card bodyStyle={{ padding: 0 }}>
        <Spin spinning={loading}>
          {rows.length === 0 && !loading ? (
            <Empty description="暂无订阅源" style={{ padding: 48 }} />
          ) : (
            <Table<SourceRow>
              rowKey="id"
              dataSource={rows}
              columns={columns}
              pagination={{ pageSize: 20, showSizeChanger: true }}
              size="middle"
            />
          )}
        </Spin>
      </Card>

      {/* —— 新增 modal —— */}
      <Modal
        title="新增 RSS 订阅源"
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        onOk={handleAddSubmit}
        okText="添加"
        cancelText="取消"
        width={640}
        destroyOnClose
      >
        <Form form={addForm} layout="vertical">
          <Form.Item
            name="subscribe_url"
            label="订阅地址 (RSS / Atom URL)"
            rules={[{ required: true, message: '请输入订阅地址' }]}
          >
            <Input
              placeholder="https://example.com/feed.xml 或 http://quantmind-rsshub:1200/..."
              addonAfter={
                <Button
                  type="link"
                  size="small"
                  icon={<EyeOutlined />}
                  loading={previewing}
                  onClick={handlePreview}
                  style={{ padding: 0 }}
                >
                  预览
                </Button>
              }
            />
          </Form.Item>

          {/* Twitter / 微博 / 雪球 RSSHub 快捷生成 */}
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="快捷生成 (走本地 RSSHub)"
            description={
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <Input
                  size="small"
                  placeholder="Twitter 用户名 (如 elonmusk)"
                  style={{ width: 180 }}
                  onPressEnter={(e) => {
                    const u = (e.target as HTMLInputElement).value.trim().replace(/^@/, '');
                    if (u) addForm.setFieldValue('subscribe_url', `http://quantmind-rsshub:1200/twitter/user/${u}`);
                  }}
                />
                <Input
                  size="small"
                  placeholder="微博用户 UID"
                  style={{ width: 160 }}
                  onPressEnter={(e) => {
                    const u = (e.target as HTMLInputElement).value.trim();
                    if (u) addForm.setFieldValue('subscribe_url', `http://quantmind-rsshub:1200/weibo/user/${u}`);
                  }}
                />
                <Input
                  size="small"
                  placeholder="雪球用户 ID"
                  style={{ width: 160 }}
                  onPressEnter={(e) => {
                    const u = (e.target as HTMLInputElement).value.trim();
                    if (u) addForm.setFieldValue('subscribe_url', `http://quantmind-rsshub:1200/xueqiu/user/${u}`);
                  }}
                />
                <Text type="secondary" style={{ fontSize: 11 }}>回车自动填入订阅地址</Text>
              </div>
            }
          />

          {previewData ? (
            <Alert
              type={previewData.subscribed ? 'warning' : 'info'}
              showIcon
              style={{ marginBottom: 16 }}
              message={previewData.title || '(无标题)'}
              description={
                <div className="space-y-1">
                  {previewData.siteLink ? (
                    <div>
                      <Text type="secondary">站点：</Text>
                      <a href={previewData.siteLink} target="_blank" rel="noreferrer">
                        {previewData.siteLink}
                      </a>
                    </div>
                  ) : null}
                  {previewData.description ? (
                    <Text type="secondary">{previewData.description}</Text>
                  ) : null}
                  {previewData.subscribed ? (
                    <Tag color="warning">该源已订阅</Tag>
                  ) : null}
                </div>
              }
            />
          ) : null}

          <Form.Item name="name" label="自定义名称（可选）">
            <Input placeholder="留空则使用源默认名称" />
          </Form.Item>

          <Form.Item name="folder_id" label="归入文件夹" initialValue={0}>
            <Select options={folderOptions} />
          </Form.Item>
        </Form>
      </Modal>

      {/* —— 编辑 modal —— */}
      <Modal
        title="编辑订阅源"
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={handleEditSubmit}
        okText="保存"
        cancelText="取消"
        width={640}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="subscribe_url" label="订阅地址">
            <Input disabled />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="folder_id" label="所在文件夹">
            <Select options={folderOptions} />
          </Form.Item>
          <Form.Item
            name="fetch_interval_minutes"
            label="抓取间隔（分钟，留空使用默认）"
          >
            <InputNumber min={1} max={1440} style={{ width: '100%' }} />
          </Form.Item>
          <Space size="large">
            <Form.Item name="enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              name="crawl_full_content"
              label="抓取全文"
              valuePropName="checked"
              tooltip="开启后 Huntly 会尝试拉取文章完整正文"
            >
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      {/* —— 文件夹管理 modal —— */}
      <Modal
        title="文件夹管理"
        open={folderOpen}
        onCancel={() => setFolderOpen(false)}
        footer={null}
        width={520}
      >
        <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
          <Input
            placeholder="新文件夹名称"
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            onPressEnter={handleAddFolder}
          />
          <Button type="primary" onClick={handleAddFolder}>新建</Button>
        </Space.Compact>

        <Table<HuntlyFolder>
          rowKey={(f) => String(f.id ?? 0)}
          size="small"
          pagination={false}
          dataSource={folders.filter((f) => f.id != null)}
          columns={[
            { title: '名称', dataIndex: 'name', key: 'name' },
            {
              title: '订阅源数',
              key: 'count',
              width: 100,
              align: 'right',
              render: (_, f) => (f.connectors || []).length,
            },
            {
              title: '操作',
              key: 'actions',
              width: 150,
              render: (_, f) => (
                <Space>
                  <Button size="small" onClick={() => handleRenameFolder(f)}>
                    重命名
                  </Button>
                  <Popconfirm
                    title={`删除文件夹「${f.name}」？源会被移到未分组`}
                    onConfirm={() => handleDeleteFolder(f)}
                    okText="删除"
                    okButtonProps={{ danger: true }}
                    cancelText="取消"
                  >
                    <Button size="small" danger>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
};

export default AdminRssSources;
