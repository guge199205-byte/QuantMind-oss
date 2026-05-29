import React, { useState, useEffect } from 'react';
import { List, Button, Tag, message, Modal, Tooltip } from 'antd';
import { LaptopOutlined, MobileOutlined, TabletOutlined, DesktopOutlined, DeleteOutlined } from '@ant-design/icons';
import { userCenterService } from '../services/userCenterService';

interface DeviceManagementProps {
    userId: string;
}

interface Device {
    id: string;
    device_name: string;
    device_type: string;
    ip_address: string;
    last_active: string;
    is_current: boolean;
    location?: string;
    os?: string;
    browser?: string;
}

export const DeviceManagement: React.FC<DeviceManagementProps> = ({ userId }) => {
    const [devices, setDevices] = useState<Device[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchDevices = async () => {
        try {
            setLoading(true);
            const data = await userCenterService.getDevices();
            // data might be wrapped or just array depending on my service impl.
            // In service I did: return this.get<any[]>('/devices');
            // If backend returns list directly, it's fine.
            setDevices(Array.isArray(data) ? data : []);
        } catch (error) {
            message.error('获取设备列表失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDevices();
    }, [userId]);

    const handleRevoke = (deviceId: string) => {
        Modal.confirm({
            title: '确认移除设备?',
            content: '移除后该设备将无法访问您的账户，需重新登录。',
            okText: '移除',
            okType: 'danger',
            cancelText: '取消',
            onOk: async () => {
                try {
                    await userCenterService.revokeDevice(deviceId);
                    message.success('设备已移除');
                    fetchDevices();
                } catch (error: any) {
                    message.error(error.message || '操作失败');
                }
            },
        });
    };

    const getIcon = (type: string) => {
        const t = type.toLowerCase();
        if (t.includes('mobile') || t.includes('phone')) return <MobileOutlined />;
        if (t.includes('tablet') || t.includes('ipad')) return <TabletOutlined />;
        if (t.includes('desktop') || t.includes('mac') || t.includes('windows')) return <DesktopOutlined />;
        return <LaptopOutlined />;
    };

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h3 className="text-lg font-bold text-slate-800">设备管理</h3>
                    <p className="text-xs text-slate-500 mt-1">管理已登录的设备与活跃会话</p>
                </div>
                <Button onClick={fetchDevices} loading={loading} size="small">刷新</Button>
            </div>

            <List
                loading={loading}
                itemLayout="horizontal"
                dataSource={devices}
                renderItem={(item) => (
                    <List.Item
                        actions={[
                            item.is_current ? (
                                <Tag color="blue">当前设备</Tag>
                            ) : (
                                <Button
                                    type="text"
                                    danger
                                    icon={<DeleteOutlined />}
                                    onClick={() => handleRevoke(item.id)}
                                >
                                    移除
                                </Button>
                            )
                        ]}
                    >
                        <List.Item.Meta
                            avatar={
                                <div className={`p-3 rounded-xl flex items-center justify-center text-xl ${item.is_current ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-500'
                                    }`}>
                                    {getIcon(item.device_type || 'desktop')}
                                </div>
                            }
                            title={
                                <div className="flex items-center gap-2">
                                    <span className="font-bold text-slate-700">
                                        {item.device_name || '未命名设备'}
                                    </span>
                                    {item.is_current && <Tag color="success" className="text-[10px] scale-90 origin-left">Current</Tag>}
                                </div>
                            }
                            description={
                                <div className="text-xs text-slate-400 space-y-1">
                                    <div>
                                        {item.location || '未知位置'} · {item.ip_address}
                                    </div>
                                    <div>
                                        最近活跃: {new Date(item.last_active).toLocaleString()}
                                    </div>
                                    {(item.os || item.browser) && (
                                        <div className="text-slate-300">
                                            {item.os} {item.browser ? `· ${item.browser}` : ''}
                                        </div>
                                    )}
                                </div>
                            }
                        />
                    </List.Item>
                )}
            />
        </div>
    );
};
