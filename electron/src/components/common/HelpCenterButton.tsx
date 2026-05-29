/**
 * 帮助中心组件
 * 统一的帮助中心入口，显示在页面左下角
 */

import React from 'react';
import { HelpCircle } from 'lucide-react';

interface HelpCenterButtonProps {
    /** 帮助页面 URL，默认为官方文档首页 */
    helpUrl?: string;
    /** 自定义类名 */
    className?: string;
}

export const HelpCenterButton: React.FC<HelpCenterButtonProps> = ({
    helpUrl = 'https://quantmind.ai/docs', // 默认官方文档地址
    className = '',
}) => {
    const handleClick = () => {
        // 在新窗口打开帮助页面
        window.open(helpUrl, '_blank', 'noopener,noreferrer');
    };

    return (
        <button
            onClick={handleClick}
            className={`
        fixed bottom-6 left-6 z-50
        flex items-center gap-2
        px-4 py-2.5
        bg-white hover:bg-gray-50
        border border-gray-200 hover:border-blue-400
        rounded-xl
        shadow-sm hover:shadow-md
        transition-all duration-200
        group
        ${className}
      `}
            title="打开帮助中心"
        >
            <HelpCircle className="w-5 h-5 text-gray-600 group-hover:text-blue-500 transition-colors" />
            <span className="text-sm font-medium text-gray-700 group-hover:text-blue-600 transition-colors">
                帮助中心
            </span>
        </button>
    );
};

export default HelpCenterButton;
