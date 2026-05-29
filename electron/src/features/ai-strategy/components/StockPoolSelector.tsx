/**
 * 股票池选择器组件
 * 支持手动输入、批量导入、搜索和智能推荐
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  Card,
  Input,
  Select,
  Button,
  Tag,
  Space,
  Row,
  Col,
  Typography,
  Tooltip,
  message,
  Upload,
  Modal,
  Table,
  Divider,
  Empty,
  AutoComplete,
  Alert,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  ImportOutlined,
  ExportOutlined,
  SearchOutlined,
  StarOutlined,
  BulbOutlined,
  ClearOutlined,
  UploadOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;

// 股票信息接口
export interface StockInfo {
  symbol: string;
  name?: string;
  market?: 'SH' | 'SZ' | 'BJ' | 'US' | 'HK';
  industry?: string;
  price?: number;
  selected?: boolean;
}

// 股票池选择器属性
export interface StockPoolSelectorProps {
  value?: string[]; // 已选择的股票代码
  onChange?: (symbols: string[]) => void; // 股票池变化回调
  maxSymbols?: number; // 最大股票数量
  market?: 'CN' | 'US' | 'HK' | 'GLOBAL'; // 市场类型
  showRecommendations?: boolean; // 是否显示推荐
  disabled?: boolean;
}

// 预设股票池
const PRESET_POOLS: Record<string, { name: string; symbols: string[]; description: string }> = {
  sh50: {
    name: '上证50',
    symbols: [
      '600000.SH', '600016.SH', '600019.SH', '600028.SH', '600030.SH',
      '600036.SH', '600048.SH', '600050.SH', '600104.SH', '600276.SH',
      '600309.SH', '600519.SH', '600887.SH', '600900.SH', '601012.SH',
      '601088.SH', '601166.SH', '601318.SH', '601328.SH', '601398.SH',
      '601601.SH', '601628.SH', '601688.SH', '601818.SH', '601857.SH',
      '601888.SH', '601899.SH', '601919.SH', '601988.SH', '601995.SH'
    ],
    description: '上证50指数成分股（部分）'
  },
  hs300: {
    name: '沪深300',
    symbols: [
      '000001.SZ', '000002.SZ', '000063.SZ', '000066.SZ', '000100.SZ',
      '000333.SZ', '000338.SZ', '000651.SZ', '000858.SZ', '000876.SZ',
      '600000.SH', '600036.SH', '600519.SH', '600887.SH', '601318.SH',
      '601398.SH', '601818.SH', '601857.SH', '601988.SH', '603259.SH'
    ],
    description: '沪深300指数成分股（部分）'
  },
  tech: {
    name: '科技龙头',
    symbols: [
      '000063.SZ', '000725.SZ', '002230.SZ', '002415.SZ', '002475.SZ',
      '300059.SZ', '300750.SZ', '600030.SH', '600048.SH', '600276.SH',
      '603160.SH', '688012.SH', '688036.SH', '688126.SH', '688981.SH'
    ],
    description: '科技行业龙头股票'
  },
  finance: {
    name: '金融板块',
    symbols: [
      '600000.SH', '600015.SH', '600016.SH', '600030.SH', '600036.SH',
      '601166.SH', '601288.SH', '601318.SH', '601328.SH', '601398.SH',
      '601601.SH', '601628.SH', '601658.SH', '601688.SH', '601818.SH'
    ],
    description: '银行、证券、保险等金融行业'
  },
  consumption: {
    name: '消费龙头',
    symbols: [
      '000333.SZ', '000568.SZ', '000858.SZ', '002304.SZ', '002572.SZ',
      '600519.SH', '600887.SH', '600900.SH', '603288.SH', '603369.SH'
    ],
    description: '大消费行业龙头股票'
  },
  us_tech: {
    name: '美股科技',
    symbols: [
      'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
      'NVDA', 'TSLA', 'AMD', 'INTC', 'NFLX'
    ],
    description: '美股科技巨头'
  },
};

// 常用股票搜索数据（实际应从后端获取）
const COMMON_STOCKS: StockInfo[] = [
  { symbol: '600519.SH', name: '贵州茅台', market: 'SH', industry: '食品饮料' },
  { symbol: '000858.SZ', name: '五粮液', market: 'SZ', industry: '食品饮料' },
  { symbol: '600036.SH', name: '招商银行', market: 'SH', industry: '银行' },
  { symbol: '601318.SH', name: '中国平安', market: 'SH', industry: '保险' },
  { symbol: '000001.SZ', name: '平安银行', market: 'SZ', industry: '银行' },
  { symbol: '600030.SH', name: '中信证券', market: 'SH', industry: '证券' },
  { symbol: '000063.SZ', name: '中兴通讯', market: 'SZ', industry: '通信' },
  { symbol: '600276.SH', name: '恒瑞医药', market: 'SH', industry: '医药' },
  { symbol: '300750.SZ', name: '宁德时代', market: 'SZ', industry: '新能源' },
  { symbol: 'AAPL', name: 'Apple Inc.', market: 'US', industry: 'Technology' },
  { symbol: 'MSFT', name: 'Microsoft Corp.', market: 'US', industry: 'Technology' },
  { symbol: 'TSLA', name: 'Tesla Inc.', market: 'US', industry: 'Automotive' },
];

export const StockPoolSelector: React.FC<StockPoolSelectorProps> = ({
  value = [],
  onChange,
  maxSymbols = 50,
  market = 'CN',
  showRecommendations = true,
  disabled = false,
}) => {
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(value);
  const [inputValue, setInputValue] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [searchResults, setSearchResults] = useState<StockInfo[]>([]);
  const [isImportModalVisible, setIsImportModalVisible] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [importedData, setImportedData] = useState<string[]>([]);

  // 同步外部value
  useEffect(() => {
    if (JSON.stringify(value) !== JSON.stringify(selectedSymbols)) {
      setSelectedSymbols(value);
    }
  }, [value]);

  // 触发onChange回调
  const handleChange = useCallback((symbols: string[]) => {
    setSelectedSymbols(symbols);
    onChange?.([...symbols]);
  }, [onChange]);

  // 添加单个股票
  const handleAddSymbol = useCallback((symbol: string) => {
    if (!symbol.trim()) {
      message.warning('请输入股票代码');
      return;
    }

    const trimmedSymbol = symbol.trim().toUpperCase();

    if (selectedSymbols.includes(trimmedSymbol)) {
      message.warning(`股票 ${trimmedSymbol} 已在池中`);
      return;
    }

    if (selectedSymbols.length >= maxSymbols) {
      message.error(`股票池已达上限 ${maxSymbols} 只`);
      return;
    }

    handleChange([...selectedSymbols, trimmedSymbol]);
    setInputValue('');
    message.success(`已添加 ${trimmedSymbol}`);
  }, [selectedSymbols, maxSymbols, handleChange]);

  // 移除单个股票
  const handleRemoveSymbol = useCallback((symbol: string) => {
    handleChange(selectedSymbols.filter(s => s !== symbol));
    message.success(`已移除 ${symbol}`);
  }, [selectedSymbols, handleChange]);

  // 清空股票池
  const handleClearAll = useCallback(() => {
    handleChange([]);
    message.success('已清空股票池');
  }, [handleChange]);

  // 加载预设股票池
  const handleLoadPreset = useCallback((presetKey: string) => {
    const preset = PRESET_POOLS[presetKey];
    if (!preset) return;

    const newSymbols = [...new Set([...selectedSymbols, ...preset.symbols])].slice(0, maxSymbols);
    handleChange(newSymbols);
    message.success(`已加载 ${preset.name}（${preset.symbols.length}只股票）`);
  }, [selectedSymbols, maxSymbols, handleChange]);

  // 股票搜索
  const handleSearch = useCallback((value: string) => {
    setSearchValue(value);

    if (!value.trim()) {
      setSearchResults([]);
      return;
    }

    const searchTerm = value.toLowerCase();
    const results = COMMON_STOCKS.filter(
      stock =>
        stock.symbol.toLowerCase().includes(searchTerm) ||
        stock.name?.toLowerCase().includes(searchTerm) ||
        stock.industry?.toLowerCase().includes(searchTerm)
    );

    setSearchResults(results);
  }, []);

  // 批量导入处理
  const handleImportConfirm = useCallback(() => {
    if (importedData.length === 0) {
      message.warning('没有可导入的数据');
      return;
    }

    const validSymbols = importedData
      .map(s => s.trim().toUpperCase())
      .filter(s => s.length > 0);

    const uniqueSymbols = [...new Set([...selectedSymbols, ...validSymbols])].slice(0, maxSymbols);

    handleChange(uniqueSymbols);
    setIsImportModalVisible(false);
    setImportedData([]);
    setFileList([]);
    message.success(`成功导入 ${validSymbols.length} 只股票`);
  }, [importedData, selectedSymbols, maxSymbols, handleChange]);

  // 文件上传处理
  const handleFileChange = (info: any) => {
    setFileList(info.fileList);

    if (info.file.status === 'done') {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        const symbols = text
          .split(/[\n,;]+/)
          .map(s => s.trim())
          .filter(s => s.length > 0);

        setImportedData(symbols);
        message.success(`成功读取 ${symbols.length} 只股票`);
      };
      reader.readAsText(info.file.originFileObj);
    }
  };

  // 导出股票池
  const handleExport = useCallback(() => {
    if (selectedSymbols.length === 0) {
      message.warning('股票池为空，无法导出');
      return;
    }

    const content = selectedSymbols.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stock_pool_${new Date().getTime()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success('股票池已导出');
  }, [selectedSymbols]);

  // 根据市场过滤预设池
  const getFilteredPresets = () => {
    if (market === 'US') {
      return { us_tech: PRESET_POOLS.us_tech };
    }
    const { us_tech, ...cnPresets } = PRESET_POOLS;
    return cnPresets;
  };

  return (
    <Card
      title={
        <Space>
          <StarOutlined />
          <span>股票池配置</span>
          <Tag color="blue">{selectedSymbols.length}/{maxSymbols}</Tag>
        </Space>
      }
      extra={
        <Space>
          <Tooltip title="导入股票">
            <Button
              icon={<ImportOutlined />}
              onClick={() => setIsImportModalVisible(true)}
              disabled={disabled}
            >
              导入
            </Button>
          </Tooltip>
          <Tooltip title="导出股票">
            <Button
              icon={<ExportOutlined />}
              onClick={handleExport}
              disabled={disabled || selectedSymbols.length === 0}
            >
              导出
            </Button>
          </Tooltip>
          <Popconfirm
            title="确定清空整个股票池吗？"
            onConfirm={handleClearAll}
            okText="确定"
            cancelText="取消"
          >
            <Button
              danger
              icon={<ClearOutlined />}
              disabled={disabled || selectedSymbols.length === 0}
            >
              清空
            </Button>
          </Popconfirm>
        </Space>
      }
    >
      {/* 添加股票输入框 */}
      <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
        <AutoComplete
          style={{ flex: 1 }}
          value={inputValue}
          onChange={setInputValue}
          onSearch={handleSearch}
          placeholder="输入股票代码或名称（如：600519.SH 或 贵州茅台）"
          options={searchResults.map(stock => ({
            value: stock.symbol,
            label: (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>
                  <strong>{stock.symbol}</strong> - {stock.name}
                </span>
                <Tag color="blue">{stock.industry}</Tag>
              </div>
            ),
          }))}
          onSelect={(value) => {
            const valueStr = typeof value === 'string' ? value : String(value);
            setInputValue(valueStr);
            handleAddSymbol(valueStr);
          }}
          disabled={disabled}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => handleAddSymbol(inputValue)}
          disabled={disabled || !inputValue.trim()}
        >
          添加
        </Button>
      </Space.Compact>

      {/* 使用说明 */}
      <Alert
        message="使用提示"
        description={
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>A股格式：代码.SH（上海）、代码.SZ（深圳）、代码.BJ（北交所）</li>
            <li>美股格式：直接输入代码，如 AAPL、MSFT</li>
            <li>支持批量导入：点击"导入"按钮上传txt文件（每行一个代码）</li>
            <li>支持预设股票池：快速加载常用板块</li>
          </ul>
        }
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      {/* 预设股票池 */}
      {showRecommendations && (
        <div style={{ marginBottom: 16 }}>
          <Divider orientation="left">
            <Space>
              <BulbOutlined />
              <span>预设股票池</span>
            </Space>
          </Divider>
          <Row gutter={[8, 8]}>
            {Object.entries(getFilteredPresets()).map(([key, preset]) => (
              <Col key={key} span={8}>
                <Tooltip title={preset.description}>
                  <Button
                    block
                    onClick={() => handleLoadPreset(key)}
                    disabled={disabled}
                  >
                    {preset.name} ({preset.symbols.length})
                  </Button>
                </Tooltip>
              </Col>
            ))}
          </Row>
        </div>
      )}

      {/* 已选择的股票池 */}
      <Divider orientation="left">
        <Space>
          <CheckCircleOutlined />
          <span>已选股票</span>
        </Space>
      </Divider>
      {selectedSymbols.length > 0 ? (
        <div style={{ maxHeight: 300, overflowY: 'auto' }}>
          <Space size={[8, 8]} wrap>
            {selectedSymbols.map(symbol => {
              const stockInfo = COMMON_STOCKS.find(s => s.symbol === symbol);
              return (
                <Tag
                  key={symbol}
                  closable={!disabled}
                  onClose={() => handleRemoveSymbol(symbol)}
                  color={stockInfo ? 'blue' : 'default'}
                >
                  {symbol}
                  {stockInfo && <Text type="secondary"> - {stockInfo.name}</Text>}
                </Tag>
              );
            })}
          </Space>
        </div>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂未选择股票，请添加或选择预设股票池"
        />
      )}

      {/* 批量导入弹窗 */}
      <Modal
        title="批量导入股票"
        open={isImportModalVisible}
        onOk={handleImportConfirm}
        onCancel={() => {
          setIsImportModalVisible(false);
          setImportedData([]);
          setFileList([]);
        }}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Alert
            message="导入格式说明"
            description="支持txt、csv文件，每行一个股票代码，或使用逗号、分号分隔"
            type="info"
            showIcon
          />

          <Upload
            fileList={fileList}
            onChange={handleFileChange}
            beforeUpload={() => false}
            accept=".txt,.csv"
            maxCount={1}
          >
            <Button icon={<UploadOutlined />} block>
              选择文件上传
            </Button>
          </Upload>

          <div>
            <Paragraph>或直接粘贴股票代码：</Paragraph>
            <Input.TextArea
              rows={6}
              placeholder="每行一个股票代码，或使用逗号、分号分隔&#10;例如：&#10;600519.SH&#10;000858.SZ&#10;AAPL,MSFT,GOOGL"
              value={importedData.join('\n')}
              onChange={(e) => {
                const symbols = e.target.value
                  .split(/[\n,;]+/)
                  .map(s => s.trim())
                  .filter(s => s.length > 0);
                setImportedData(symbols);
              }}
            />
            {importedData.length > 0 && (
              <Text type="secondary">
                已识别 {importedData.length} 只股票
              </Text>
            )}
          </div>
        </Space>
      </Modal>
    </Card>
  );
};

export default StockPoolSelector;
