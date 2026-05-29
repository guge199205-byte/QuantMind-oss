import React, { useState, useCallback } from 'react';
import { motion, Reorder } from 'framer-motion';
import { Settings, Maximize2, Minimize2, RotateCcw, Save } from 'lucide-react';

interface DashboardModule {
  id: string;
  title: string;
  component: React.ComponentType | null;
  size: 'small' | 'medium' | 'large';
  position: { x: number; y: number };
  isVisible: boolean;
}

interface DashboardCustomizerProps {
  modules: DashboardModule[];
  onModulesChange: (modules: DashboardModule[]) => void;
  onSaveLayout: () => void;
  onResetLayout: () => void;
}

export const DashboardCustomizer: React.FC<DashboardCustomizerProps> = ({
  modules,
  onModulesChange,
  onSaveLayout,
  onResetLayout
}) => {
  const [isCustomizing, setIsCustomizing] = useState(false);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);

  const handleModuleReorder = useCallback((newOrder: DashboardModule[]) => {
    onModulesChange(newOrder);
  }, [onModulesChange]);

  const handleToggleVisibility = useCallback((moduleId: string) => {
    const updatedModules = modules.map(module =>
      module.id === moduleId
        ? { ...module, isVisible: !module.isVisible }
        : module
    );
    onModulesChange(updatedModules);
  }, [modules, onModulesChange]);

  const handleSizeChange = useCallback((moduleId: string, size: 'small' | 'medium' | 'large') => {
    const updatedModules = modules.map(module =>
      module.id === moduleId
        ? { ...module, size }
        : module
    );
    onModulesChange(updatedModules);
  }, [modules, onModulesChange]);

  const handleStartCustomizing = () => {
    setIsCustomizing(true);
  };

  const handleStopCustomizing = () => {
    setIsCustomizing(false);
    setSelectedModule(null);
  };

  const handleSaveAndExit = () => {
    onSaveLayout();
    handleStopCustomizing();
  };

  if (!isCustomizing) {
    return (
      <motion.button
        onClick={handleStartCustomizing}
        className="fixed bottom-20 right-4 z-50 p-3 bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-colors"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <Settings className="w-5 h-5" />
      </motion.button>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 z-50 flex"
    >
      {/* 控制面板 */}
      <motion.div
        initial={{ x: -300 }}
        animate={{ x: 0 }}
        exit={{ x: -300 }}
        className="w-80 bg-white shadow-2xl p-6 overflow-y-auto"
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-gray-800">仪表盘定制</h3>
          <button
            onClick={handleStopCustomizing}
            className="text-gray-500 hover:text-gray-700"
          >
            <Minimize2 className="w-5 h-5" />
          </button>
        </div>

        {/* 模块列表 */}
        <div className="space-y-4">
          <h4 className="font-semibold text-gray-700 mb-3">模块管理</h4>

          <Reorder.Group
            axis="y"
            values={modules}
            onReorder={handleModuleReorder}
            className="space-y-2"
          >
            {modules.map((module) => (
              <Reorder.Item
                key={module.id}
                value={module}
                className={`p-3 border rounded-lg cursor-move transition-all ${
                  selectedModule === module.id
                    ? 'border-blue-500 bg-blue-50'
                    : module.isVisible
                    ? 'border-gray-200 bg-white'
                    : 'border-gray-200 bg-gray-50'
                }`}
                whileDrag={{ scale: 1.05, boxShadow: '0 10px 30px rgba(0,0,0,0.2)' }}
                onClick={() => setSelectedModule(module.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={module.isVisible}
                      onChange={() => handleToggleVisibility(module.id)}
                      className="w-4 h-4 text-blue-600"
                    />
                    <span className={`font-medium ${
                      module.isVisible ? 'text-gray-800' : 'text-gray-400'
                    }`}>
                      {module.title}
                    </span>
                  </div>
                  <div className="flex space-x-1">
                    {['small', 'medium', 'large'].map((size) => (
                      <button
                        key={size}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSizeChange(module.id, size as any);
                        }}
                        className={`px-2 py-1 text-xs rounded ${
                          module.size === size
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                        }`}
                      >
                        {size === 'small' ? 'S' : size === 'medium' ? 'M' : 'L'}
                      </button>
                    ))}
                  </div>
                </div>
              </Reorder.Item>
            ))}
          </Reorder.Group>
        </div>

        {/* 操作按钮 */}
        <div className="mt-8 space-y-3">
          <button
            onClick={handleSaveAndExit}
            className="w-full flex items-center justify-center space-x-2 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Save className="w-4 h-4" />
            <span>保存布局</span>
          </button>

          <button
            onClick={onResetLayout}
            className="w-full flex items-center justify-center space-x-2 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            <span>重置布局</span>
          </button>

          <button
            onClick={handleStopCustomizing}
            className="w-full py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
        </div>
      </motion.div>

      {/* 预览区域 */}
      <div className="flex-1 p-6 bg-gray-100">
        <div className="h-full bg-white rounded-lg p-4 overflow-hidden">
          <h4 className="text-lg font-semibold text-gray-800 mb-4">布局预览</h4>

          {/* 网格预览 */}
          <div className="grid grid-cols-3 gap-4 h-5/6">
            {modules
              .filter(module => module.isVisible)
              .map((module, index) => (
                <motion.div
                  key={module.id}
                  className={`
                    border-2 border-dashed rounded-lg flex items-center justify-center text-center
                    ${selectedModule === module.id ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'}
                    ${module.size === 'small' ? 'h-20' : module.size === 'medium' ? 'h-32' : 'h-44'}
                  `}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.1 }}
                  onClick={() => setSelectedModule(module.id)}
                >
                  <div>
                    <p className="font-medium text-gray-700">{module.title}</p>
                    <p className="text-sm text-gray-500 capitalize">{module.size}</p>
                  </div>
                </motion.div>
              ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
};
