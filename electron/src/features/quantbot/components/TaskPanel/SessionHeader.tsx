/**
 * SessionHeader - 新建对话按钮组件
 */

import React from 'react';
import { Plus } from 'lucide-react';

interface SessionHeaderProps {
    onNewChat: () => void;
    loading?: boolean;
}

const SessionHeader: React.FC<SessionHeaderProps> = ({ onNewChat, loading = false }) => {
    return (
        <div className="px-3 py-3 border-b border-gray-200 bg-gradient-to-br from-white to-gray-50/50">
            <button
                onClick={onNewChat}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5
                   bg-gradient-to-r from-blue-500 to-purple-600 text-white
                   rounded-xl hover:shadow-lg hover:scale-[1.02] transition-all
                   font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <Plus className="w-4 h-4" />
                <span>{loading ? '创建中...' : '新建对话'}</span>
            </button>
        </div>
    );
};

export default SessionHeader;
