import React, { useState, useEffect, useRef } from 'react';
import { 
  Table, 
  Button, 
  Input, 
  Space, 
  Typography, 
  message, 
  Upload, 
  Tag, 
  Flex, 
  Modal,
  Popconfirm
} from 'antd';
import { 
  ImportOutlined, 
  SaveOutlined, 
  DeleteOutlined, 
  SearchOutlined
} from '@ant-design/icons';
import { useWizardV2Store } from '../store/wizardV2Store';
import { parseAndMatchStocks, StockIndexItem } from '../utils/stockImport';
import { loadFeaturesBySymbolsInBatches } from '../utils/featureEnrichment';

const { Text } = Typography;

export const StockPoolTable: React.FC = () => {
  const { 
    workingPool, 
    currentPoolName, 
    setCurrentPoolName, 
    saveCurrentPoolAsVersion, 
    removeWorkingPoolItem,
    addWorkingPoolItem,
    setWorkingPool,
  } = useWizardV2Store();
  
  const [loading, setLoading] = useState(false);
  const [stockIndex, setStockIndex] = useState<StockIndexItem[]>([]);
  const [searchText, setSearchText] = useState('');
  const [autoRefreshing, setAutoRefreshing] = useState(false);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [pendingImported, setPendingImported] = useState(false);
  const [saveName, setSaveName] = useState(currentPoolName || '我的股票池');
  const lastHydratedKeyRef = useRef<string>('');

  useEffect(() => {
    const loadIndex = async () => {
      try {
        const response = await fetch('/data/stocks/stocks_index.json');
        if (!response.ok) throw new Error('Failed to load stock index');
        const data = await response.json();
        setStockIndex(data.items || []);
      } catch (err) {
        console.error('Error loading stock index:', err);
      }
    };
    loadIndex();
  }, []);

  useEffect(() => {
    const hydrateMissingFeatures = async () => {
      if (autoRefreshing || !workingPool?.length) return;
      const symbols = workingPool.map((s) => s.symbol).filter(Boolean);
      if (!symbols.length) return;

      const key = symbols.join(',');
      if (key && key === lastHydratedKeyRef.current) return;

      const needHydrate = workingPool.some((s) => {
        const marketCap = Number(s.marketCap);
        const pe = Number((s as any).pe);
        return !Number.isFinite(marketCap) || marketCap <= 0 || !Number.isFinite(pe) || pe === 0;
      });
      if (!needHydrate) return;

      try {
        setAutoRefreshing(true);
        const richData = await loadFeaturesBySymbolsInBatches(symbols);
        if (!richData.length) return;
        const richMap = new Map(richData.map((item) => [item.code, item]));

        const merged = workingPool.map((stock) => {
          const item: any = richMap.get(stock.symbol);
          if (!item) return stock;
          return {
            ...stock,
            name: stock.name || item.name || stock.symbol,
            marketCap: Number(stock.marketCap) > 0 ? stock.marketCap : item.marketCap,
            pe: Number((stock as any).pe) !== 0
              ? (stock as any).pe
              : (item.pe ?? item.pe_ttm ?? item.peTtm ?? 0),
            roe: stock.roe ?? item.roe,
            price: stock.price ?? item.closePrice,
          };
        });
        setWorkingPool(merged as any);
        lastHydratedKeyRef.current = key;
      } catch (err) {
        console.warn('[StockPoolTable] auto refresh features failed:', err);
      } finally {
        setAutoRefreshing(false);
      }
    };

    hydrateMissingFeatures();
  }, [workingPool, autoRefreshing, setWorkingPool]);

  const handleImport = async (file: File) => {
    if (stockIndex.length === 0) {
      message.warning('正在初始化股票索引，请稍后再试');
      return false;
    }
    
    setLoading(true);
    try {
        // 默认回退到第1列（索引0）解析代码，防止无表头单列数据解析失败
        const importedStocks = await parseAndMatchStocks(file, stockIndex, 0);
      if (importedStocks.length === 0) {
        message.warning('未在指定列解析到有效的股票代码');
      } else {
        const symbols = importedStocks.map(s => s.symbol);
        message.loading({ content: '正在同步投研特征数据...', key: 'syncData', duration: 0 });
        const richData = await loadFeaturesBySymbolsInBatches(symbols);
        
        const existingSymbols = new Set((workingPool || []).map(s => s.symbol));
        const newItems: any[] = [];
        
        richData.forEach(item => {
          if (!existingSymbols.has(item.code)) {
            newItems.push({
              symbol: item.code,
              name: item.name,
              marketCap: item.marketCap,
              pe: (item as any).pe ?? (item as any).pe_ttm ?? (item as any).peTtm,
              roe: item.roe,
              price: item.closePrice
            });
            existingSymbols.add(item.code);
          }
        });

        const foundSymbols = new Set(richData.map(d => d.code));
        importedStocks.forEach(s => {
          if (!foundSymbols.has(s.symbol) && !existingSymbols.has(s.symbol)) {
            newItems.push(s);
            existingSymbols.add(s.symbol);
          }
        });

        if (newItems.length > 0) {
          setWorkingPool([...(workingPool || []), ...newItems]);
        }

        message.success({ content: `成功导入 ${importedStocks.length} 只股票，已同步最新特征`, key: 'syncData' });
        setPendingImported(true);
        setSaveName(currentPoolName || '我的股票池');
        message.info('已导入新股票池，请点击“保存”并命名后同步到云端');
      }
    } catch (err) {
      message.error('导入失败: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
    return false;
  };

  const savePoolToCloud = async (poolName: string) => {
    if (!poolName.trim()) {
      message.error('请输入股票池名称');
      return;
    }
    if (!workingPool || workingPool.length === 0) {
      message.warning('当前列表为空');
      return;
    }

    const success = await saveCurrentPoolAsVersion(poolName.trim());
    if (success) {
      setCurrentPoolName(poolName.trim());
      message.success(`股票池 "${poolName.trim()}" 已保存并同步到云端`);
      setPendingImported(false);
    } else {
      message.error('保存失败，请检查网络后重试');
    }
  };

  const handleSavePool = async () => {
    if (pendingImported) {
      setSaveName(currentPoolName || '我的股票池');
      setSaveModalOpen(true);
      return;
    }
    await savePoolToCloud(currentPoolName || '我的股票池');
  };

  const handleSaveWithName = async () => {
    await savePoolToCloud(saveName);
    setSaveModalOpen(false);
  };

  const columns = [
    {
      title: '代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: '18%',
      align: 'center' as const,
      render: (text: string) => (
        <Tag style={{ margin: 0, fontFamily: 'Roboto Mono', fontWeight: 600, background: '#f5f5f5', border: 'none' }}>
          {text}
        </Tag>
      ),
    },
    {
      title: '简称',
      dataIndex: 'name',
      key: 'name',
      width: '18%',
      align: 'center' as const,
      sorter: (a: any, b: any) => (a.name || '').localeCompare(b.name || ''),
      render: (text: string) => <Text strong style={{ color: '#1e293b' }}>{text}</Text>
    },
    {
      title: '市值 (亿)',
      dataIndex: 'marketCap',
      key: 'marketCap',
      width: '18%',
      align: 'center' as const,
      sorter: (a: any, b: any) => (a.marketCap || 0) - (b.marketCap || 0),
      render: (val: number) => (
        <Text style={{ fontFamily: 'Roboto Mono', fontWeight: 500 }}>
          {val ? val.toFixed(2) : '--'}
        </Text>
      ),
    },
    {
      title: '市盈率',
      dataIndex: 'pe',
      key: 'pe',
      width: '18%',
      align: 'center' as const,
      sorter: (a: any, b: any) => ((a.pe || 0) - (b.pe || 0)),
      render: (val: number) => {
        if (val === undefined || val === null || !Number.isFinite(Number(val)) || Number(val) === 0) {
          return <Text type="secondary">--</Text>;
        }
        return <Text style={{ fontFamily: 'Roboto Mono', fontWeight: 500 }}>{Number(val).toFixed(2)}</Text>;
      },
    },
    {
      title: '最新价',
      dataIndex: 'price',
      key: 'price',
      width: '18%',
      align: 'center' as const,
      render: (val: number) => val ? (
        <Text style={{ fontFamily: 'Roboto Mono', fontWeight: 600, color: '#1d39c4' }}>
          {val.toFixed(2)}
        </Text>
      ) : '--',
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      align: 'center' as const,
      render: (_: any, record: any) => (
        <Popconfirm
          title="确认移除？"
          onConfirm={() => removeWorkingPoolItem(record.symbol)}
          okText="移除"
          cancelText="取消"
        >
          <Button 
            type="text" 
            danger 
            icon={<DeleteOutlined style={{ fontSize: 12 }} />} 
            size="small"
          />
        </Popconfirm>
      ),
    },
  ];

  const filteredStocks = (workingPool || []).filter(s => 
    s.symbol.toLowerCase().includes(searchText.toLowerCase()) || 
    (s.name || '').toLowerCase().includes(searchText.toLowerCase())
  );

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 紧凑型工具栏 */}
      <div style={{ marginBottom: 12 }}>
        <Flex justify="space-between" align="center" wrap="wrap" gap={12}>
          <Space size={12}>
            <Input 
              placeholder="名称..." 
              value={currentPoolName} 
              onChange={e => setCurrentPoolName(e.target.value)}
              style={{
                width: 120,
                fontWeight: 600,
                borderRadius: 6,
                fontSize: '12px',
                borderColor: '#dfe5ef',
                boxShadow: 'none',
              }}
              size="small"
            />
            <span style={{ borderLeft: '1px solid #f0f0f0', height: 14, margin: '0 4px' }} />
            <Text type="secondary" style={{ fontSize: 11 }}>
              资产数: <Text strong style={{ color: '#1890ff' }}>{workingPool?.length || 0}</Text>
            </Text>
          </Space>

          <Space size={8}>
            <Input 
              placeholder="搜索..." 
              prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />} 
              onChange={e => setSearchText(e.target.value)}
              style={{ width: 140, borderRadius: 6 }}
              size="small"
              allowClear
            />
            <Upload accept=".csv" showUploadList={false} beforeUpload={handleImport}>
              <Button icon={<ImportOutlined />} loading={loading} size="small">导入</Button>
            </Upload>
            <Button 
              type="primary" 
              icon={<SaveOutlined />} 
              onClick={handleSavePool} 
              size="small"
              style={{ borderRadius: 6 }}
            >
              保存
            </Button>
          </Space>
        </Flex>
      </div>

      {/* 表格区域 - 自动填充高度 */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Table
          dataSource={filteredStocks}
          columns={columns}
          rowKey="symbol"
          size="small"
          pagination={{ 
            pageSize: 10, 
            showSizeChanger: true, 
            size: 'small',
            showTotal: (total) => `共 ${total} 只`
          }}
          scroll={{ y: 'calc(100vh - 480px)' }}
          className="elegant-stock-table"
        />
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .elegant-stock-table .ant-table-thead > tr > th {
          background: #fbfbfb !important;
          font-weight: 600;
          font-size: 12px;
          padding: 10px 8px !important;
        }
        .elegant-stock-table .ant-table-cell {
          padding: 8px 8px !important;
        }
        .elegant-stock-table .ant-table-row:hover {
          background-color: #f0faff !important;
        }
      `}} />

      <Modal
        title="保存股票池"
        open={saveModalOpen}
        onCancel={() => setSaveModalOpen(false)}
        onOk={handleSaveWithName}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Input
          value={saveName}
          onChange={(e) => setSaveName(e.target.value)}
          placeholder="请输入股票池名称"
          maxLength={64}
        />
      </Modal>
    </div>
  );
};
