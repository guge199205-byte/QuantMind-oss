/**
 * 会话管理页面
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Tag,
  Space,
  Popconfirm,
  message,
  Alert,
  Descriptions,
  Modal,
} from 'antd';
import {
  LaptopOutlined,
  MobileOutlined,
  TabletOutlined,
  DesktopOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { SERVICE_ENDPOINTS } from '../../../config/services';

interface UserSession {
  id: number;
  user_id: string;
  session_token: string;
  device_type: string;
  device_name: string;
  ip_address: string;
  user_agent: string;
  is_current: boolean;
  last_activity: string;
  created_at: string;
  expires_at: string;
}

interface SessionManagementPageProps {
  userId: string;
}

import { Laptop, Smartphone, Tablet, Monitor, ShieldCheck, ShieldAlert, Eye, Trash2, Info } from 'lucide-react';

const SessionManagementPage: React.FC<SessionManagementPageProps> = ({ userId }) => {
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedSession, setSelectedSession] = useState<UserSession | null>(null);

  useEffect(() => {
    fetchSessions();
  }, [userId]);

  const API_BASE = SERVICE_ENDPOINTS.USER_SERVICE;

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/${userId}/sessions`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('获取会话列表失败');
      }

      const data = await response.json();
      setSessions(data.data.sessions || []);
    } catch (error: any) {
      message.error(error.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTerminateSession = async (sessionId: number) => {
    try {
      const response = await fetch(
        `${API_BASE}/users/${userId}/sessions/${sessionId}`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('终止会话失败');
      }

      message.success('会话已终止');
      fetchSessions();
    } catch (error: any) {
      message.error(error.message || '操作失败');
    }
  };

  const handleTerminateAllOtherSessions = async () => {
    try {
      const response = await fetch(
        `${API_BASE}/users/${userId}/sessions/terminate-others`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('终止其他会话失败');
      }

      message.success('所有其他会话已终止');
      fetchSessions();
    } catch (error: any) {
      message.error(error.message || '操作失败');
    }
  };

  const getDeviceIcon = (deviceType: string) => {
    switch (deviceType?.toLowerCase()) {
      case 'mobile':
        return <Smartphone className="w-4 h-4" />;
      case 'tablet':
        return <Tablet className="w-4 h-4" />;
      case 'desktop':
        return <Monitor className="w-4 h-4" />;
      default:
        return <Laptop className="w-4 h-4" />;
    }
  };

  const parseUserAgent = (userAgent: string) => {
    if (!userAgent) return '未知浏览器';
    if (userAgent.includes('Chrome')) return 'Chrome';
    if (userAgent.includes('Firefox')) return 'Firefox';
    if (userAgent.includes('Safari')) return 'Safari';
    if (userAgent.includes('Edge')) return 'Edge';
    return '未知浏览器';
  };

  const columns: ColumnsType<UserSession> = [
    {
      title: '访问设备',
      key: 'device',
      width: 240,
      render: (_, record) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-50 flex items-center justify-center text-slate-400 border border-slate-100 shadow-inner">
            {getDeviceIcon(record.device_type)}
          </div>
          <div>
            <div className="text-sm font-bold text-slate-700">{record.device_name || '未知设备'}</div>
            <div className="text-[10px] font-black text-slate-300 uppercase tracking-widest">
              {parseUserAgent(record.user_agent)}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 120,
      render: (_, record) =>
        record.is_current ? (
          <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-emerald-100 flex items-center gap-1.5 w-fit">
            <ShieldCheck className="w-3 h-3" /> 当前会话
          </span>
        ) : (
          <span className="px-2 py-0.5 bg-blue-50 text-blue-500 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-blue-100 flex items-center gap-1.5 w-fit">
            活跃中
          </span>
        ),
    },
    {
      title: 'IP 地址',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 150,
      render: (text: string) => <span className="text-xs font-bold text-slate-500 font-mono tracking-tight">{text}</span>,
    },
    {
      title: '最后活动于',
      dataIndex: 'last_activity',
      key: 'last_activity',
      width: 180,
      render: (text: string) => <span className="text-[11px] font-bold text-slate-400 font-mono">{new Date(text).toLocaleString('zh-CN')}</span>,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      fixed: 'right' as const,
      render: (_, record) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              setSelectedSession(record);
              setDetailModalVisible(true);
            }}
            className="p-2 hover:bg-slate-50 text-slate-400 hover:text-slate-600 rounded-xl transition-colors"
            title="会话详情"
          >
            <Eye size={16} />
          </button>
          {!record.is_current && (
            <Popconfirm
              title="确定终止此会话吗?"
              onConfirm={() => handleTerminateSession(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <button
                className="p-2 hover:bg-rose-50 text-slate-400 hover:text-rose-500 rounded-xl transition-colors"
                title="终止会话"
              >
                <Trash2 size={16} />
              </button>
            </Popconfirm>
          )}
        </div>
      ),
    },
  ];

  const hasOtherSessions = sessions.filter((s) => !s.is_current).length > 0;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100 bg-slate-50/50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Monitor className="w-5 h-5 text-indigo-500" />
            <h2 className="text-base font-black text-slate-800 uppercase tracking-widest">活跃会话管理</h2>
          </div>
          {hasOtherSessions && (
            <Popconfirm
              title="确定终止所有其他会话吗?"
              description="这将登出所有其他设备，但不会影响当前会话。"
              onConfirm={handleTerminateAllOtherSessions}
              okText="确定"
              cancelText="取消"
            >
              <button className="px-4 py-1.5 bg-rose-50 text-rose-600 border border-rose-100 rounded-xl font-bold text-xs hover:bg-rose-100 transition-all">
                终止所有其他会话
              </button>
            </Popconfirm>
          )}
        </div>

        <div className="p-8">
          <div className="bg-blue-50 p-4 rounded-xl flex items-start gap-3 border border-blue-100 mb-8">
            <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
            <div className="text-xs text-blue-700 leading-relaxed font-medium">
              安全提示：如果发现不认识的设备或位置，请立即终止相应会话并修改您的账户密码。
            </div>
          </div>

          <div className="rounded-2xl border border-gray-100 overflow-hidden shadow-inner bg-slate-50/20">
            <Table
              columns={columns}
              dataSource={sessions}
              rowKey="id"
              loading={loading}
              className="custom-modern-table"
              pagination={{
                pageSize: 10,
                showTotal: (total) => <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Active Sessions: {total}</span>,
              }}
              scroll={{ x: 1000 }}
            />
          </div>
        </div>
      </div>

      {/* 会话详情对话框 */}
      <Modal
        title={
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-500" />
            <span className="font-black text-slate-800">会话安全明细</span>
          </div>
        }
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <button
            key="close"
            onClick={() => setDetailModalVisible(false)}
            className="px-6 py-2 bg-slate-100 text-slate-600 rounded-xl font-bold text-sm mr-2 hover:bg-slate-200 transition-all"
          >
            关闭详情
          </button>,
          selectedSession && !selectedSession.is_current && (
            <Popconfirm
              key="terminate"
              title="确定终止此会话吗?"
              onConfirm={() => {
                handleTerminateSession(selectedSession.id);
                setDetailModalVisible(false);
              }}
              okText="确定"
              cancelText="取消"
            >
              <button className="px-6 py-2 bg-rose-500 text-white rounded-xl font-bold text-sm shadow-lg shadow-rose-500/20 hover:bg-rose-600 transition-all">
                立即终止该会话
              </button>
            </Popconfirm>
          ),
        ]}
        width={640}
        className="custom-modern-modal"
      >
        {selectedSession && (
          <div className="py-4 space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">Session ID</span>
                <span className="text-sm font-bold text-slate-700 font-mono">#{selectedSession.id}</span>
              </div>
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">IP Address</span>
                <span className="text-sm font-bold text-slate-700 font-mono">{selectedSession.ip_address}</span>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-gray-100 bg-slate-50/50 flex items-center justify-between">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Device Identity</span>
                <span className="px-2 py-0.5 bg-white border border-slate-200 rounded-lg text-[9px] font-black uppercase text-slate-400">Trusted Device</span>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-400">设备名称</span>
                  <span className="text-sm font-black text-slate-700">{selectedSession.device_name || '未知设备'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-400">浏览器内核</span>
                  <span className="text-sm font-black text-slate-700">{parseUserAgent(selectedSession.user_agent)}</span>
                </div>
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-bold text-slate-400">User Agent</span>
                  <code className="p-3 bg-slate-50 border border-slate-100 rounded-lg text-[10px] font-mono font-medium text-slate-500 break-all leading-relaxed">
                    {selectedSession.user_agent || '未知'}
                  </code>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Session Created</span>
                <span className="text-xs font-bold text-slate-600 font-mono">{new Date(selectedSession.created_at).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Last Activity</span>
                <span className="text-xs font-bold text-emerald-500 font-mono">{new Date(selectedSession.last_activity).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center pt-3 border-t border-slate-200">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Security Status</span>
                <span className={`text-[10px] font-black uppercase ${selectedSession.is_current ? 'text-emerald-500' : 'text-blue-500'}`}>
                  {selectedSession.is_current ? 'Authenticated · Active now' : 'Persistent · Idle'}
                </span>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default SessionManagementPage;
