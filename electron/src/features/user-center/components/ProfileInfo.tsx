import React, { useState, useEffect } from 'react';
import { Form, Input, Button, message, Spin, Upload, Avatar, Alert } from 'antd';
import { UserOutlined, UploadOutlined } from '@ant-design/icons';
import { useProfile } from '../hooks';
import type { UserProfileUpdate } from '../types';
import { useAuth } from '../../auth/hooks';

interface ProfileInfoProps {
    userId: string;
}

export const ProfileInfo: React.FC<ProfileInfoProps> = ({ userId }) => {
    const [form] = Form.useForm();
    const [isEditing, setIsEditing] = useState(false);
    const { user } = useAuth();

    const {
        profile,
        isLoading,
        error,
        updateProfile,
        uploadAvatar,
        avatarUploadStatus,
        avatarUploadProgress,
        updateStatus,
    } = useProfile(userId);

    // 初始化表单数据
    useEffect(() => {
        if (profile) {
            form.setFieldsValue({
                username: profile.username || user?.username || '',
                email: profile.email || user?.email || '',
                bio: profile.bio || '',
                location: profile.location || '',
                website: profile.website || '',
            });
        }
    }, [profile, user, form]);

    const handleSave = async () => {
        try {
            const values = await form.validateFields();
            await updateProfile(values as UserProfileUpdate);
            message.success('档案已更新');
            setIsEditing(false);
        } catch (err: any) {
            console.error('保存失败:', err);
            message.error(err.message || '更新失败');
        }
    };

    const handleAvatarUpload = async (file: File) => {
        try {
            await uploadAvatar(file);
            message.success('头像上传成功');
            return false; // 阻止默认上传行为
        } catch (err: any) {
            message.error(err.message || '上传失败');
            return false;
        }
    };

    if (isLoading) {
        return (
            <>
                <Form form={form} component={false} />
                <div style={{ textAlign: 'center', padding: 50 }}>
                    <Spin size="large" tip="加载中...">
                        <div style={{ padding: 20 }} />
                    </Spin>
                </div>
            </>
        );
    }

    if (error) {
        return (
            <>
                <Form form={form} component={false} />
                <Alert message="提示" description={error} type="warning" showIcon />
            </>
        );
    }

    if (!profile) {
        return (
            <>
                <Form form={form} component={false} />
                <Alert message="提示" description="暂无档案数据" type="info" showIcon />
            </>
        );
    }

    return (
        <div style={{ display: 'flex', gap: 20 }}>
            {/* 左侧：头像和账号信息 */}
            <div style={{ width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
                {/* 头像区域 */}
                <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
                    <Avatar size={90} icon={<UserOutlined />} src={profile.avatar} className="shadow-lg border-4 border-white mb-4" />
                    <Upload
                        showUploadList={false}
                        beforeUpload={(file) => {
                            handleAvatarUpload(file);
                            return false;
                        }}
                        accept="image/*"
                    >
                        <Button
                            loading={avatarUploadStatus === 'loading'}
                            className="rounded-xl font-bold"
                            icon={<UploadOutlined />}
                        >
                            {avatarUploadStatus === 'loading' ? `${Math.round(avatarUploadProgress)}%` : '更换头像'}
                        </Button>
                    </Upload>
                </div>

                {/* 账号信息 */}
                <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
                    <h4 className="mb-3 text-xs font-bold text-slate-800 uppercase tracking-wider">账号信息</h4>
                    <div className="text-xs space-y-2">
                        <div className="flex justify-between">
                            <span className="text-slate-400 font-medium">用户ID</span>
                            <span className="font-mono text-slate-700">{profile.user_id}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-400 font-medium">交易经验</span>
                            <span className="font-bold text-slate-700">
                                {profile.trading_experience === 'beginner'
                                    ? '初级'
                                    : profile.trading_experience === 'intermediate'
                                        ? '中级'
                                        : '高级'}
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-400 font-medium">注册时间</span>
                            <span className="text-slate-700">{new Date(profile.created_at).toLocaleDateString()}</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* 右侧：表单区域 */}
            <div className="flex-1 bg-white rounded-xl border border-gray-200 p-5 shadow-sm flex flex-col">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-sm font-bold text-slate-800">基本资料</h3>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        {isEditing ? '● Editing Mode' : 'Read Only'}
                    </span>
                </div>

                <div className="flex-1">
                    <Form
                        form={form}
                        layout="vertical"
                        size="middle"
                    >
                        <div className="grid grid-cols-2 gap-4">
                            <Form.Item
                                name="username"
                                label={<span className="text-xs font-bold text-slate-500">用户名</span>}
                                rules={[{ required: true, message: '请输入用户名' }]}
                            >
                                <Input disabled={!isEditing} className="rounded-lg" />
                            </Form.Item>

                            <Form.Item
                                name="email"
                                label={<span className="text-xs font-bold text-slate-500">邮箱</span>}
                            >
                                <Input disabled className="rounded-lg" />
                            </Form.Item>

                            <Form.Item
                                name="location"
                                label={<span className="text-xs font-bold text-slate-500">所在地</span>}
                            >
                                <Input disabled={!isEditing} placeholder="例如: 北京" className="rounded-lg" />
                            </Form.Item>

                            <Form.Item
                                name="website"
                                label={<span className="text-xs font-bold text-slate-500">个人网站</span>}
                            >
                                <Input disabled={!isEditing} placeholder="https://" className="rounded-lg" />
                            </Form.Item>
                        </div>

                        <Form.Item
                            name="bio"
                            label={<span className="text-xs font-bold text-slate-500">个人简介</span>}
                        >
                            <Input.TextArea disabled={!isEditing} rows={3} placeholder="介绍一下自己..." className="rounded-lg" />
                        </Form.Item>

                        <Form.Item className="mb-0">
                            {isEditing ? (
                                <div className="flex gap-2">
                                    <Button
                                        type="primary"
                                        onClick={handleSave}
                                        loading={updateStatus === 'loading'}
                                        className="rounded-lg bg-blue-600 font-bold px-6"
                                    >
                                        保存更新
                                    </Button>
                                    <Button
                                        onClick={() => setIsEditing(false)}
                                        className="rounded-lg font-bold"
                                    >
                                        取消
                                    </Button>
                                </div>
                            ) : (
                                <Button
                                    type="primary"
                                    onClick={() => setIsEditing(true)}
                                    className="rounded-lg bg-slate-800 border-none font-bold px-6"
                                >
                                    编辑档案
                                </Button>
                            )}
                        </Form.Item>
                    </Form>
                </div>
            </div>
        </div>
    );
};
