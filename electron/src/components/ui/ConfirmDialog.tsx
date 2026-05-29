import React from 'react';
import ReactDOM from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDialogProps {
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    onCancel: () => void;
    confirmText?: string;
    cancelText?: string;
    isDanger?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
    isOpen,
    title,
    message,
    onConfirm,
    onCancel,
    confirmText = '确定',
    cancelText = '取消',
    isDanger = false,
}) => {
    if (typeof document === 'undefined') return null;

    return ReactDOM.createPortal(
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-[9999] flex items-center justify-center pointer-events-none">
                    {/* 背景遮罩 */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-black/40 backdrop-blur-sm pointer-events-auto"
                        onClick={onCancel}
                    />

                    {/* 对话框内容 */}
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 10 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 10 }}
                        transition={{ type: 'spring', damping: 25, stiffness: 350 }}
                        className="relative bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden pointer-events-auto border border-gray-100"
                    >
                        {/* 顶部标题栏 */}
                        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
                            <div className="flex items-center gap-2">
                                {isDanger && <AlertTriangle className="w-5 h-5 text-amber-500" />}
                                <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
                            </div>
                            <button
                                onClick={onCancel}
                                className="p-1 hover:bg-gray-200 rounded-full transition-colors text-gray-400 hover:text-gray-600"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* 内容区域 */}
                        <div className="px-6 py-6">
                            <p className="text-gray-600 leading-relaxed text-sm">
                                {message}
                            </p>
                        </div>

                        {/* 按钮区域 */}
                        <div className="px-6 py-4 bg-gray-50 flex items-center justify-end gap-3">
                            <button
                                onClick={onCancel}
                                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                {cancelText}
                            </button>
                            <button
                                onClick={onConfirm}
                                className={`px-4 py-2 text-sm font-medium text-white rounded-lg shadow-sm transition-all ${isDanger
                                        ? 'bg-rose-500 hover:bg-rose-600 shadow-rose-500/20'
                                        : 'bg-blue-600 hover:bg-blue-700 shadow-blue-500/20'
                                    }`}
                            >
                                {confirmText}
                            </button>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>,
        document.body
    );
};
