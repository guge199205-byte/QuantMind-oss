import React from 'react';
import { motion } from 'framer-motion';

export const DashboardSkeleton: React.FC = () => {
    return (
        // background 用 inline style 确保渐变生效（Tailwind bg-[] 生成 background-color，无法承载 linear-gradient CSS 变量）
        <div className="w-full h-full relative overflow-hidden" style={{ background: 'var(--bg-gradient)' }}>
            {/* 顶部标题栏 Skeleton */}
            <div className="h-20 w-full px-6 flex items-center justify-between border-b border-[var(--border-primary)]/10 bg-[var(--nav-bg)] backdrop-blur-md">
                <div className="h-8 w-48 bg-gray-200/20 rounded animate-pulse" />
                <div className="flex gap-4">
                    <div className="h-8 w-8 bg-gray-200/20 rounded-full animate-pulse" />
                    <div className="h-8 w-8 bg-gray-200/20 rounded-full animate-pulse" />
                </div>
            </div>

            {/* 主要内容区域 Skeleton */}
            <div
                className="grid gap-4 p-4 overflow-hidden"
                style={{
                    height: 'calc(100% - 164px)',
                    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                    gridAutoRows: '400px'
                }}
            >
                {/* 生成 6 个卡片占位符 */}
                {Array.from({ length: 6 }).map((_, i) => (
                    <div
                        key={i}
                        className="w-full h-full rounded-2xl p-1 relative overflow-hidden bg-[var(--bg-card)]/40 backdrop-blur-md border border-[var(--border-card)]"
                    >
                        <div className="w-full h-full flex flex-col p-4 space-y-4">
                            {/* 卡片标题 */}
                            <div className="w-1/3 h-6 bg-gray-200/10 rounded animate-pulse" />

                            {/* 卡片内容区 */}
                            <div className="flex-1 w-full bg-gray-200/5 rounded-xl animate-pulse" />
                        </div>
                    </div>
                ))}
            </div>

            {/* 底部导航栏占位 */}
            <div className="fixed bottom-4 left-1/2 transform -translate-x-1/2 w-96 h-16 bg-[var(--nav-bg)] backdrop-blur-md rounded-2xl border border-[var(--nav-border)] animate-pulse" />
        </div>
    );
};
