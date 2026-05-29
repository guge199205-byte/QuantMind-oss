/**
 * 登录历史页面
 */

import React, { useState, useEffect } from 'react';
import { Card, Table, Tag, Space, Button, DatePicker, Select, message, Alert } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LaptopOutlined,
  MobileOutlined,
  GlobalOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { RangePickerProps } from 'antd/es/date-picker';
import dayjs, { Dayjs } from 'dayjs';
import { SERVICE_ENDPOINTS } from '../../../config/services';

const { RangePicker } = DatePicker;

interface LoginHistory {
  id: number;
  user_id: string;
  login_type: 'password' | 'mfa' | 'sso';
  success: boolean;
  ip_address: string;
  location?: string;
  device_type: string;
  device_name: string;
  user_agent: string;
  failure_reason?: string;
  created_at: string;
}

interface LoginHistoryPageProps {
  userId: string;
}

import { Laptop, Smartphone, ShieldCheck, ShieldAlert, MapPin, Search, Calendar, RefreshCw, AlertTriangle } from 'lucide-react';

const LoginHistoryPage: React.FC<LoginHistoryPageProps> = ({ userId }) => {
  const [history, setHistory] = useState<LoginHistory[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const [filters, setFilters] = useState<{
    success?: boolean;
    login_type?: string;
    date_range?: [string, string];
  }>({});

  useEffect(() => {
    fetchLoginHistory();
  }, [userId, pagination.current, pagination.pageSize, filters]);

  const API_BASE = SERVICE_ENDPOINTS.USER_SERVICE;

  const fetchLoginHistory = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: pagination.current.toString(),
        page_size: pagination.pageSize.toString(),
        ...(filters.success !== undefined && { success: filters.success.toString() }),
        ...(filters.login_type && { login_type: filters.login_type }),
        ...(filters.date_range && {
          start_date: filters.date_range[0],
          end_date: filters.date_range[1],
        }),
      });

      const response = await fetch(
        `${API_BASE}/users/${userId}/login-history?${params}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('获取登录历史失败');
      }

      const data = await response.json();
      setHistory(data.data.history || []);
      setPagination({
        ...pagination,
        total: data.data.pagination?.total || 0,
      });
    } catch (error: any) {
      message.error(error.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTableChange = (newPagination: any) => {
    setPagination({
      current: newPagination.current,
      pageSize: newPagination.pageSize,
      total: pagination.total,
    });
  };

  const handleDateRangeChange: RangePickerProps['onChange'] = (dates) => {
    if (dates && dates[0] && dates[1]) {
      setFilters({
        ...filters,
        date_range: [dates[0].format('YYYY-MM-DD'), dates[1].format('YYYY-MM-DD')],
      });
    } else {
      const { date_range, ...rest } = filters;
      setFilters(rest);
    }
    setPagination({ ...pagination, current: 1 });
  };

  const handleSuccessFilterChange = (value: boolean | undefined) => {
    if (value === undefined) {
      const { success, ...rest } = filters;
      setFilters(rest);
    } else {
      setFilters({ ...filters, success: value });
    }
    setPagination({ ...pagination, current: 1 });
  };

  const handleLoginTypeFilterChange = (value: string | undefined) => {
    if (value === undefined) {
      const { login_type, ...rest } = filters;
      setFilters(rest);
    } else {
      setFilters({ ...filters, login_type: value });
    }
    setPagination({ ...pagination, current: 1 });
  };

  const getDeviceIcon = (deviceType: string) => {
    return deviceType?.toLowerCase() === 'mobile' ? <Smartphone className="w-4 h-4" /> : <Laptop className="w-4 h-4" />;
  };

  const parseUserAgent = (userAgent: string) => {
    if (!userAgent) return '未知浏览器';
    if (userAgent.includes('Chrome')) return 'Chrome';
    if (userAgent.includes('Firefox')) return 'Firefox';
    if (userAgent.includes('Safari')) return 'Safari';
    if (userAgent.includes('Edge')) return 'Edge';
    return '未知浏览器';
  };

  const columns: ColumnsType<LoginHistory> = [
    {
      title: '状态',
      key: 'success',
      width: 100,
      render: (_, record) =>
        record.success ? (
          <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-emerald-100 flex items-center gap-1 w-fit">
            <ShieldCheck className="w-3 h-3" /> 成功
          </span>
        ) : (
          <span className="px-2 py-0.5 bg-rose-50 text-rose-600 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-rose-100 flex items-center gap-1 w-fit">
            <ShieldAlert className="w-3 h-3" /> 失败
          </span>
        ),
    },
    {
      title: '登录方式',
      dataIndex: 'login_type',
      key: 'login_type',
      width: 120,
      render: (type: string) => {
        const typeMap: Record<string, { bg: string; color: string; text: string }> = {
          password: { bg: 'bg-blue-50', color: 'text-blue-600', text: '密码登录' },
          mfa: { bg: 'bg-emerald-50', color: 'text-emerald-600', text: 'MFA认证' },
          sso: { bg: 'bg-purple-50', color: 'text-purple-600', text: 'SSO单点' },
        };
        const config = typeMap[type] || { bg: 'bg-slate-50', color: 'text-slate-400', text: type };
        return (
          <span className={`px-2 py-0.5 rounded-lg text-[10px] font-bold uppercase tracking-widest ${config.bg} ${config.color}`}>
            {config.text}
          </span>
        );
      },
    },
    {
      title: '设备/环境',
      key: 'device',
      width: 240,
      render: (_, record) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-50 flex items-center justify-center text-slate-400 border border-slate-100">
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
      title: 'IP / 归属地',
      key: 'ip',
      width: 200,
      render: (_, record) => (
        <div className="flex flex-col gap-1">
          <span className="text-xs font-bold text-slate-500 font-mono tracking-tight">{record.ip_address}</span>
          {record.location && (
            <span className="text-[10px] font-bold text-slate-300 flex items-center gap-1 uppercase tracking-tighter">
              <MapPin className="w-3 h-3" /> {record.location}
            </span>
          )}
        </div>
      ),
    },
    {
      title: '操作时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => <span className="text-[11px] font-bold text-slate-400 font-mono">{new Date(text).toLocaleString('zh-CN')}</span>,
    },
    {
      title: '安全备注',
      dataIndex: 'failure_reason',
      key: 'failure_reason',
      render: (reason: string) =>
        reason ? <span className="text-[10px] font-black uppercase text-rose-400 bg-rose-50 px-2 py-0.5 rounded-md">{reason}</span> : <span className="text-slate-200">—</span>,
    },
  ];

  const failedAttempts = history.filter((h) => !h.success).length;
  const suspiciousActivity = history.some((h) => !h.success && h.failure_reason);

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100 bg-slate-50/50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-indigo-500" />
            <h2 className="text-base font-black text-slate-800 uppercase tracking-widest">账户登录历史</h2>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex flex-col items-end">
              <span className="text-base font-black text-slate-800 leading-none">{pagination.total}</span>
              <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest mt-1">Total Logins</span>
            </div>
            <div className="w-[1px] h-8 bg-gray-200" />
            <div className="flex flex-col items-end">
              <span className={`text-base font-black leading-none ${failedAttempts > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>{failedAttempts}</span>
              <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest mt-1">Failed Attempts</span>
            </div>
          </div>
        </div>

        <div className="p-8">
          {suspiciousActivity && (
            <div className="bg-rose-50 p-4 rounded-xl flex items-start gap-3 border border-rose-100 mb-8">
              <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
              <div className="text-xs text-rose-700 leading-relaxed font-bold">
                检测到异常登录尝试：系统记录到近期存在失败的登录行为。如果这些操作并非由您发起，请立即修改核心密码并强制开启 MFA 认证。
              </div>
            </div>
          )}

          {/* 筛选器 */}
          <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
            <div className="flex items-center gap-3">
              <RangePicker
                onChange={handleDateRangeChange}
                className="rounded-xl h-10 border-gray-200 shadow-sm"
              />
              <Select
                placeholder="状态过滤"
                allowClear
                className="w-32 custom-select-xl"
                onChange={handleSuccessFilterChange}
                variant="borderless"
              >
                <Select.Option value={true}>登录成功</Select.Option>
                <Select.Option value={false}>尝试失败</Select.Option>
              </Select>
              <Select
                placeholder="方式过滤"
                allowClear
                className="w-32 custom-select-xl"
                onChange={handleLoginTypeFilterChange}
                variant="borderless"
              >
                <Select.Option value="password">密码方式</Select.Option>
                <Select.Option value="mfa">MFA认证</Select.Option>
                <Select.Option value="sso">SSO授权</Select.Option>
              </Select>
            </div>

            <button
              onClick={fetchLoginHistory}
              className="flex items-center gap-2 px-6 py-2 bg-slate-900 text-white rounded-xl font-bold text-sm hover:bg-slate-800 transition-all shadow-md active:scale-95"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>同步历史记录</span>
            </button>
          </div>

          <div className="rounded-2xl border border-gray-100 overflow-hidden shadow-inner bg-slate-50/20">
            <Table
              columns={columns}
              dataSource={history}
              rowKey="id"
              loading={loading}
              className="custom-modern-table"
              pagination={{
                ...pagination,
                showSizeChanger: true,
                showTotal: (total) => <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Showing {total} Login Events</span>,
              }}
              onChange={handleTableChange}
              scroll={{ x: 1200 }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginHistoryPage;
