import React, { useState, useEffect } from 'react';
import { Table, Tag, message } from 'antd';
import type { TableProps } from 'antd';
import { userCenterService } from '../services/userCenterService';

interface AuditLog {
    id: string;
    action: string;
    resource: string;
    resource_id?: string;
    success: boolean; // Changed from status string to success boolean
    ip_address: string;
    user_agent?: string;
    created_at: string;
    details?: string;
}

interface AuditLogTableProps {
    userId: string;
}

export const AuditLogTable: React.FC<AuditLogTableProps> = ({ userId }) => {
    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [loading, setLoading] = useState(false);
    const [pagination, setPagination] = useState({
        current: 1,
        pageSize: 10,
        total: 0,
    });

    const fetchLogs = async (page = 1, pageSize = 10) => {
        try {
            setLoading(true);
            const res = await userCenterService.getAuditLogs({ page, pageSize });
            setLogs(res.logs || []);
            setPagination({ current: page, pageSize, total: res.total || 0 });
        } catch (error) {
            console.error('获取日志失败', error);
            message.error('获取日志失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLogs(pagination.current, pagination.pageSize);
    }, [userId]);

    const handleTableChange: TableProps<AuditLog>['onChange'] = (newPagination) => {
        fetchLogs(newPagination.current || 1, newPagination.pageSize || 10);
    };

    const columns: TableProps<AuditLog>['columns'] = [
        {
            title: '时间',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 180,
            render: (text) => new Date(text).toLocaleString(),
        },
        {
            title: '操作',
            dataIndex: 'action',
            key: 'action',
            render: (text) => <span className="font-bold text-slate-700">{text}</span>,
        },
        {
            title: '资源',
            dataIndex: 'resource',
            key: 'resource',
            render: (text, record) => (
                <span className="text-xs text-slate-500 font-mono">
                    {text} {record.resource_id ? `#${record.resource_id}` : ''}
                </span>
            ),
        },
        {
            title: 'IP地址',
            dataIndex: 'ip_address',
            key: 'ip_address',
            width: 140,
            render: (text) => <span className="font-mono text-xs">{text}</span>,
        },
        {
            title: '状态',
            key: 'status',
            width: 100,
            render: (_, record) => (
                <Tag color={record.success ? 'success' : 'error'}>
                    {record.success ? '成功' : '失败'}
                </Tag>
            ),
        },
    ];

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-bold text-slate-800">操作日志</h3>
                <span className="text-xs text-slate-400">最近30天的操作记录</span>
            </div>
            <Table
                columns={columns}
                dataSource={logs}
                rowKey="id"
                pagination={pagination}
                loading={loading}
                onChange={handleTableChange}
                size="small"
                className="text-xs"
                scroll={{ x: 800 }}
            />
        </div>
    );
};
