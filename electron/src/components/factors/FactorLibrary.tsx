/**
 * 因子库管理
 * 保存和加载因子表达式
 */

import React, { useState, useEffect } from 'react';
import { Save, FolderOpen, Trash2, Download, Upload } from 'lucide-react';

interface SavedFactor {
  id: string;
  name: string;
  expression: string;
  description?: string;
  createdAt: string;
}

interface Props {
  onLoad: (expression: string, name: string) => void;
}

export const FactorLibrary: React.FC<Props> = ({ onLoad }) => {
  const [savedFactors, setSavedFactors] = useState<SavedFactor[]>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [newFactor, setNewFactor] = useState({ name: '', expression: '', description: '' });

  useEffect(() => {
    loadFactors();
  }, []);

  const loadFactors = () => {
    const saved = localStorage.getItem('qlib_factor_library');
    if (saved) {
      try {
        setSavedFactors(JSON.parse(saved));
      } catch (error) {
        console.error('Failed to load factors:', error);
      }
    }
  };

  const saveFactor = () => {
    if (!newFactor.name || !newFactor.expression) {
      alert('请输入因子名称和表达式');
      return;
    }

    const factor: SavedFactor = {
      id: Date.now().toString(),
      name: newFactor.name,
      expression: newFactor.expression,
      description: newFactor.description,
      createdAt: new Date().toISOString(),
    };

    const updated = [...savedFactors, factor];
    setSavedFactors(updated);
    localStorage.setItem('qlib_factor_library', JSON.stringify(updated));
    setShowSaveDialog(false);
    setNewFactor({ name: '', expression: '', description: '' });
  };

  const deleteFactor = (id: string) => {
    if (confirm('确定删除此因子？')) {
      const updated = savedFactors.filter(f => f.id !== id);
      setSavedFactors(updated);
      localStorage.setItem('qlib_factor_library', JSON.stringify(updated));
    }
  };

  const exportFactors = () => {
    const dataStr = JSON.stringify(savedFactors, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `qlib_factors_${Date.now()}.json`;
    link.click();
  };

  const importFactors = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target?.result as string);
        setSavedFactors([...savedFactors, ...imported]);
        localStorage.setItem('qlib_factor_library', JSON.stringify([...savedFactors, ...imported]));
        alert('导入成功');
      } catch (error) {
        alert('导入失败：文件格式错误');
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-gray-800">因子库</h3>
        <div className="flex gap-2">
          <button onClick={() => setShowSaveDialog(true)} className="px-3 py-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm flex items-center gap-1">
            <Save className="w-3 h-3" />
            保存
          </button>
          <button onClick={exportFactors} className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm flex items-center gap-1">
            <Download className="w-3 h-3" />
            导出
          </button>
          <label className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm flex items-center gap-1 cursor-pointer">
            <Upload className="w-3 h-3" />
            导入
            <input type="file" accept=".json" onChange={importFactors} className="hidden" />
          </label>
        </div>
      </div>

      {showSaveDialog && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-2">
          <input type="text" value={newFactor.name} onChange={(e) => setNewFactor({ ...newFactor, name: e.target.value })} placeholder="因子名称" className="w-full px-3 py-2 border rounded text-sm" />
          <textarea value={newFactor.expression} onChange={(e) => setNewFactor({ ...newFactor, expression: e.target.value })} placeholder="因子表达式" rows={2} className="w-full px-3 py-2 border rounded text-sm font-mono" />
          <input type="text" value={newFactor.description} onChange={(e) => setNewFactor({ ...newFactor, description: e.target.value })} placeholder="描述（可选）" className="w-full px-3 py-2 border rounded text-sm" />
          <div className="flex gap-2">
            <button onClick={saveFactor} className="px-3 py-1.5 bg-blue-500 text-white rounded text-sm">保存</button>
            <button onClick={() => setShowSaveDialog(false)} className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-sm">取消</button>
          </div>
        </div>
      )}

      <div className="space-y-2 max-h-60 overflow-y-auto">
        {savedFactors.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            <FolderOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p className="text-sm">暂无保存的因子</p>
          </div>
        ) : (
          savedFactors.map((factor) => (
            <div key={factor.id} className="bg-gray-50 border rounded-lg p-3 hover:bg-gray-100 transition-colors">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-medium text-sm text-gray-800">{factor.name}</div>
                  <div className="text-xs text-gray-600 font-mono mt-1">{factor.expression}</div>
                  {factor.description && <div className="text-xs text-gray-500 mt-1">{factor.description}</div>}
                </div>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => onLoad(factor.expression, factor.name)}
                    aria-label={`加载 ${factor.name}`}
                    title={`加载 ${factor.name}`}
                    className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                  >
                    <FolderOpen className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteFactor(factor.id)}
                    aria-label={`删除 ${factor.name}`}
                    title={`删除 ${factor.name}`}
                    className="p-1 text-red-600 hover:bg-red-50 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
