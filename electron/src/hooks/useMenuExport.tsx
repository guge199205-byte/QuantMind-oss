import { useEffect, useState } from 'react';
import { DataExportModal } from '../components/common/DataExportModal';
import { DataExportService } from '../components/common/DataExportModal';

export const useMenuExport = () => {
  const [showExportModal, setShowExportModal] = useState(false);

  useEffect(() => {
    if (window.electronAPI) {
      const cleanup = window.electronAPI.onMenuExportData(() => {
        setShowExportModal(true);
      });

      return cleanup;
    }
  }, []);

  const handleExport = async (options: any) => {
    try {
      await DataExportService.exportData(options);
      if (window.electronAPI) {
        window.electronAPI.showNotification('导出完成', '数据已成功导出');
      }
    } catch (error) {
      console.error('导出失败:', error);
      if (window.electronAPI) {
        window.electronAPI.showNotification('导出失败', '数据导出过程中出现错误');
      }
    }
  };

  const ExportModal = showExportModal ? (
    <DataExportModal
      isOpen={showExportModal}
      onClose={() => setShowExportModal(false)}
      onExport={handleExport}
    />
  ) : null;

  return { ExportModal };
};
