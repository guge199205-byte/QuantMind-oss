import React from 'react';
import { motion } from 'framer-motion';
import { Construction, LineChart, Shield, Zap } from 'lucide-react';

export const TradingPlaceholder: React.FC = () => {
    return (
        <div className="w-full h-full flex flex-col items-center justify-center bg-gray-50/50 p-8">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="text-center max-w-2xl"
            >
                <div className="w-24 h-24 mx-auto bg-gradient-to-br from-blue-500 to-indigo-600 rounded-3xl shadow-xl flex items-center justify-center mb-8 transform rotate-3 hover:rotate-6 transition-transform">
                    <Construction className="w-12 h-12 text-white" />
                </div>

                <h1 className="text-4xl font-bold text-gray-900 mb-4 tracking-tight">
                    实盘交易系统升级中
                </h1>

                <p className="text-lg text-gray-500 mb-12 leading-relaxed">
                    我们正在重构分布式实盘交易架构，采用 Redis 中间件与 K8s 执行环境，
                    为您提供更隔离、更高效、更安全的交易体验。
                </p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
                    <div className="p-6 bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                        <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center mb-4">
                            <Shield className="w-5 h-5 text-blue-600" />
                        </div>
                        <h3 className="font-semibold text-gray-900 mb-2">隔离环境</h3>
                        <p className="text-sm text-gray-500">基于 K8s 与 API 安全网关的多租户强隔离环境</p>
                    </div>

                    <div className="p-6 bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                        <div className="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center mb-4">
                            <Zap className="w-5 h-5 text-indigo-600" />
                        </div>
                        <h3 className="font-semibold text-gray-900 mb-2">极速通信</h3>
                        <p className="text-sm text-gray-500">Redis Stream 驱动的实时信号推送与亚秒级响应</p>
                    </div>

                    <div className="p-6 bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                        <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center mb-4">
                            <LineChart className="w-5 h-5 text-purple-600" />
                        </div>
                        <h3 className="font-semibold text-gray-900 mb-2">Qlib 引擎</h3>
                        <p className="text-sm text-gray-500">深度集成的 Qlib 框架，支持全自动 AI 策略执行</p>
                    </div>
                </div>

                <div className="mt-12 flex items-center justify-center gap-2 text-sm text-gray-400">
                    <span className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
                    <span>系统设计方案已完成，正在开发中...</span>
                </div>
            </motion.div>
        </div>
    );
};

export default TradingPlaceholder;
