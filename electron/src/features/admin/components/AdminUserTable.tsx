import React, { useEffect, useState } from 'react';
import { Table, Tag, Button, Space, message, Popconfirm, Input } from 'antd';
import { adminService } from '../services/adminService';
import { AdminUser } from '../types';

export const AdminUserTable: React.FC = () => {
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchText, setSearchText] = useState('');

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async (query?: string) => {
        setLoading(true);
        try {
            const data = await adminService.listUsers(query);
            setUsers(data);
        } catch (err) {
            message.error('加载用户列表失败');
        } finally {
            setLoading(false);
        }
    };

    const handleToggleStatus = async (userId: string) => {
        try {
            const success = await adminService.toggleUserStatus(userId);
            if (success) {
                message.success('状态已更新');
                loadUsers();
            }
        } catch (err) {
            message.error('操作失败');
        }
    };

    const handleSearch = (value: string) => {
        const query = value.trim();
        setSearchText(query);
        loadUsers(query || undefined);
    };

    const columns = [
        {
            title: '用户ID',
            dataIndex: 'user_id',
            key: 'user_id',
            render: (id: string) => <code className="text-[10px] text-slate-400">{id}</code>
        },
        {
            title: '用户名',
            dataIndex: 'username',
            key: 'username',
            render: (name: string, record: AdminUser) => (
                <div>
                    <div className="font-bold text-slate-800">{name}</div>
                    <div className="text-[10px] text-slate-400">{record.email}</div>
                </div>
            )
        },
        {
            title: '身份',
            dataIndex: 'is_admin',
            key: 'is_admin',
            render: (isAdmin: boolean) => (
                <Tag color={isAdmin ? 'blue' : 'default'} className="font-bold text-[10px]">
                    {isAdmin ? '管理员' : '普通用户'}
                </Tag>
            )
        },
        {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            render: (isActive: boolean) => (
                <Space size="small">
                    <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                    <span className="text-xs">{isActive ? '正常' : '禁用'}</span>
                </Space>
            )
        },
        {
            title: '操作',
            key: 'action',
            align: 'right' as const,
            render: (_: any, record: AdminUser) => (
                <Popconfirm
                    title={record.is_active ? '确定禁用该用户吗？' : '确定启用该用户吗？'}
                    onConfirm={() => handleToggleStatus(record.user_id)}
                    okText="确定"
                    cancelText="取消"
                >
                    <Button
                        size="small"
                        type={record.is_active ? 'link' : 'primary'}
                        danger={record.is_active}
                    >
                        {record.is_active ? '禁用' : '启用'}
                    </Button>
                </Popconfirm>
            ),
        },
    ];

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-slate-800">用户管理</h3>
                <Space.Compact style={{ width: 300 }}>
                    <Input
                        placeholder="搜索用户名/ID"
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        onPressEnter={() => handleSearch(searchText)}
                        allowClear
                    />
                    <Button onClick={() => handleSearch(searchText)}>
                        搜索
                    </Button>
                </Space.Compact>
            </div>
            <Table
                columns={columns}
                dataSource={users}
                rowKey="user_id"
                loading={loading}
                pagination={{ pageSize: 12 }}
                className="border border-slate-100 rounded-xl overflow-hidden shadow-sm"
            />
        </div>
    );
};
