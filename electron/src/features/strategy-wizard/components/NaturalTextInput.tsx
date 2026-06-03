import React, { useState, useMemo } from 'react';
import { Row, Col, Card, Typography, Input, Button, Space, Alert, Tabs, Tag, Divider, message } from 'antd';
import {
  BulbOutlined,
  EditOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  StockOutlined,
  SendOutlined
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizardV2Store } from '../store/wizardV2Store';
import { fetchWorkingPoolByDsl, syncWorkingPoolToBackend } from '../services/wizardV2Service';
// 按需加载 wizardService 的网络与解析方法，避免静态与动态导入混用导致的打包警告
import { FACTORS } from '../factors/dictionary';
import { SimpleLogicBuilder } from './SimpleLogicBuilder';
import { CustomStockSelector } from './CustomStockSelector';
import { useAppSelector } from '../../../store';
import { selectCurrentMarket, type AppMarket } from '../../../store/slices/uiSlice';
import { getMarketConfig } from '../../../config/marketConfig';

const { Title, Text } = Typography;
const { TextArea } = Input;

export const NaturalTextInput: React.FC<{ onNext: () => void }> = ({ onNext }) => {
  const { workingPool, setWorkingPool, conditions, setConditions } = useWizardV2Store();
  const currentMarket = useAppSelector(selectCurrentMarket);
  // V2 specific: we use setWorkingPool instead of setPool/setConditions etc.
  // For simplicity during migration, we might still need some V1 states if UI depends on them
  // but let's try to stick to SSOT.

  const [activeTab, setActiveTab] = useState('nlp');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<{ dsl?: string; mapping?: any; suggestions?: string[] }>({});
  const [matchedCount, setMatchedCount] = useState<number | null>(null);
  const [templateCategory, setTemplateCategory] = useState<string>('all');

  const useTemplate = (t: string) => {
    setText(t);
  };

  // 按市场组织的快速模板
  const MARKET_TEMPLATES: Record<AppMarket, Record<string, { label: string; value: string }[]>> = {
    CN: {
      宽基指数: [
        { label: '全部A股', value: '全市场A股，剔除停牌和退市股票' },
        { label: '沪深300', value: '沪深300成分股' },
        { label: '中证500', value: '中证500成分股' },
        { label: '中证800', value: '中证800成分股' },
        { label: '中证1000', value: '中证1000成分股' },
        { label: '中证2000', value: '中证2000成分股' },
        { label: '上证50', value: '上证50成分股' },
        { label: '科创50', value: '科创50成分股' },
        { label: '创业板指', value: '创业板指数成分股' },
        { label: '北证50', value: '北证50成分股' },
      ],
      规模与流动性: [
        { label: '排除ST', value: '排除ST、*ST和退市风险警示股' },
        { label: '剔除新股', value: '上市满180天的股票' },
        { label: '小市值', value: '总市值10亿到100亿之间，剔除ST' },
        { label: '中市值', value: '总市值100亿到500亿之间' },
        { label: '大市值', value: '总市值大于500亿的蓝筹股' },
        { label: '高流动性', value: '日均成交额大于2亿元，换手率大于2%' },
      ],
      行业板块: [
        { label: '金融股', value: '银行、证券、保险板块' },
        { label: '医药生物', value: '医药生物行业，剔除ST' },
        { label: '消费白马', value: '食品饮料和家电行业，ROE大于15%' },
        { label: '新能源车', value: '新能源汽车产业链相关股票' },
        { label: '半导体', value: '半导体和电子元器件行业' },
        { label: '人工智能', value: 'AI、算力、大模型概念股' },
        { label: '军工', value: '国防军工行业' },
        { label: '光伏储能', value: '光伏、储能、风电相关公司' },
        { label: '券商', value: '证券行业，剔除ST' },
        { label: '银行股', value: '银行业，市净率小于1.5' },
      ],
      价值与成长: [
        { label: '低估值', value: '市盈率小于20，市净率小于2，剔除亏损' },
        { label: '深度价值', value: 'PE小于15，PB小于1.5，股息率大于3%' },
        { label: '高分红', value: '股息率大于4%，连续3年分红' },
        { label: '高ROE', value: 'ROE连续3年大于15%，资产负债率小于60%' },
        { label: '成长股', value: '净利润同比增长大于30%，营收增长大于20%' },
        { label: 'GARP', value: 'PE小于25且净利润增速大于20%，PEG小于1' },
        { label: '现金奶牛', value: '经营现金流净额连续3年为正，毛利率大于40%' },
      ],
      技术形态: [
        { label: '突破新高', value: '近20日创60日新高，成交量放大' },
        { label: '均线多头', value: '5日均线>10日均线>20日均线>60日均线' },
        { label: 'MACD金叉', value: 'MACD金叉，DIF穿越DEA向上' },
        { label: '超跌反弹', value: 'RSI小于30且近5日上涨' },
        { label: '回踩均线', value: '股价回踩20日均线企稳' },
        { label: '强势股', value: '近20日涨幅前10%，剔除ST' },
      ],
      资金趋势: [
        { label: '北向加仓', value: '近5日北向资金净流入排名前100' },
        { label: '主力流入', value: '主力资金净流入连续3日为正' },
        { label: '机构重仓', value: '机构持股比例大于30%' },
        { label: '融资买入', value: '融资余额近5日持续增加' },
      ],
      主题热点: [
        { label: '高ROE+低估值', value: 'ROE大于15%且PE小于20，市值大于100亿' },
        { label: '低估蓝筹', value: '沪深300且PE小于15且股息率大于3%' },
        { label: '困境反转', value: '近1季度净利润同比扭亏，PB小于2' },
        { label: '小盘成长', value: '市值小于100亿，营收增长大于30%' },
        { label: 'AI算力', value: '云计算、IDC、服务器相关，市值大于50亿' },
      ],
    },
    HK: {
      宽基指数: [
        { label: '全部港股', value: '全市场港股，剔除停牌和退市股票' },
        { label: '恒生指数', value: '恒生指数成分股' },
        { label: '恒生科技', value: '恒生科技指数成分股' },
        { label: '恒生国企', value: '恒生中国企业指数成分股' },
        { label: '恒生中小盘', value: '恒生中小盘指数成分股' },
      ],
      规模与流动性: [
        { label: '剔除仙股', value: '股价大于1港元的股票' },
        { label: '大市值', value: '总市值大于500亿港元的蓝筹股' },
        { label: '中市值', value: '总市值50亿到500亿港元之间' },
        { label: '高流动性', value: '日均成交额大于5000万港元' },
      ],
      行业板块: [
        { label: '金融股', value: '银行、保险、券商板块' },
        { label: '科技股', value: '互联网、软件、硬件科技公司' },
        { label: '消费股', value: '消费品和零售行业' },
        { label: '地产股', value: '房地产行业' },
        { label: '医药股', value: '医药和生物科技行业' },
        { label: '新能源', value: '新能源和清洁能源相关' },
      ],
      价值与成长: [
        { label: '低估值', value: '市盈率小于15，市净率小于1.5' },
        { label: '高分红', value: '股息率大于4%' },
        { label: '高ROE', value: 'ROE大于15%' },
        { label: '成长股', value: '净利润同比增长大于25%' },
      ],
      南向资金: [
        { label: '南向加仓', value: '近5日南向资金净流入排名前50' },
        { label: 'AH溢价', value: 'A股相对H股溢价大于30%' },
        { label: '港股通标的', value: '港股通标的股票' },
      ],
    },
    US: {
      宽基指数: [
        { label: '全部美股', value: '全市场美股，剔除停牌和退市股票' },
        { label: 'S&P 500', value: '标普500成分股' },
        { label: 'Nasdaq 100', value: '纳斯达克100成分股' },
        { label: 'Dow 30', value: '道琼斯30成分股' },
        { label: 'Russell 2000', value: '罗素2000成分股' },
      ],
      规模与流动性: [
        { label: '大盘股', value: '市值大于100亿美元的股票' },
        { label: '中盘股', value: '市值10亿到100亿美元之间' },
        { label: '小盘股', value: '市值小于10亿美元' },
        { label: '高流动性', value: '日均成交额大于1亿美元' },
      ],
      行业板块: [
        { label: '科技巨头', value: 'FAANG+微软+英伟达' },
        { label: '半导体', value: '半导体和芯片行业' },
        { label: 'AI概念', value: '人工智能和机器学习相关' },
        { label: '生物医药', value: '生物科技和制药行业' },
        { label: '金融', value: '银行、保险、投行' },
        { label: '消费', value: '消费品和零售行业' },
        { label: '能源', value: '石油、天然气、新能源' },
      ],
      价值与成长: [
        { label: '低估值', value: 'PE小于20，PB小于3' },
        { label: '高分红', value: '股息率大于3%' },
        { label: '高增长', value: '营收增长大于30%' },
        { label: '盈利增长', value: '净利润同比增长大于25%' },
      ],
      主题热点: [
        { label: 'AI算力', value: 'GPU、数据中心、云计算相关' },
        { label: '减肥药概念', value: 'GLP-1药物相关公司' },
        { label: '自动驾驶', value: '自动驾驶和电动车相关' },
      ],
    },
    CRYPTO: {
      主流币: [
        { label: '全部加密货币', value: '全市场加密货币，剔除退市币种' },
        { label: 'Top 10', value: '市值排名前10的加密货币' },
        { label: 'Top 20', value: '市值排名前20的加密货币' },
        { label: 'Top 50', value: '市值排名前50的加密货币' },
      ],
      按类型: [
        { label: 'Layer 1', value: '底层公链代币（ETH、SOL、AVAX等）' },
        { label: 'Layer 2', value: '二层扩展方案代币（ARB、OP等）' },
        { label: 'DeFi蓝筹', value: 'DeFi协议代币（UNI、AAVE、MKR等）' },
        { label: '稳定币相关', value: '稳定币和RWA相关代币' },
        { label: 'Meme币', value: 'Meme概念代币（DOGE、SHIB等）' },
        { label: 'AI概念', value: 'AI和机器学习相关代币' },
      ],
      规模与流动性: [
        { label: '大市值', value: '市值大于100亿美元' },
        { label: '中市值', value: '市值10亿到100亿美元之间' },
        { label: '高流动性', value: '24小时交易额大于1亿美元' },
      ],
      链上指标: [
        { label: 'TVL排名', value: 'TVL排名前20的DeFi协议代币' },
        { label: '活跃地址增长', value: '近30日活跃地址增长大于20%' },
        { label: '巨鲸持仓', value: '巨鲸地址持仓集中度大于50%' },
      ],
    },
  };

  const templateGroups = useMemo(() => MARKET_TEMPLATES[currentMarket] || MARKET_TEMPLATES.CN, [currentMarket]);

  const flatTemplates = Object.entries(templateGroups).flatMap(([cat, items]) =>
    items.map((t) => ({ ...t, category: cat })),
  );
  const visibleTemplates =
    templateCategory === 'all'
      ? flatTemplates
      : flatTemplates.filter((t) => t.category === templateCategory);

  const analyze = async () => {
    if (!text.trim()) {
      message.warning('请先输入选股描述');
      return;
    }
    setLoading(true);
    setMatchedCount(null);
    try {
      const { parseText } = await import('../services/wizardService');
      const parsed = await parseText(text, currentMarket);
      
      // 针对数据库按“元”存储的情况，修复 DSL 中的单位换算（AI 通常输出以“亿”为单位的数字）
      let correctedDsl = parsed.dsl;
      if (correctedDsl) {
        const billionFactors = FACTORS.filter(f => f.unit === '亿').map(f => f.key);
        billionFactors.forEach(f => {
          const regex = new RegExp(`(${f}\\s*(?:>|<|>=|<=|==)\\s*)(\\d+(\\.\\d+)?)`, 'g');
          correctedDsl = correctedDsl.replace(regex, (match, p1, p2) => {
            const val = parseFloat(p2);
            // 如果数值已经很大（大于100万），说明后端可能已经做过单位换算，不再重复计算
            if (val > 1000000) return match;
            return p1 + Math.floor(val * 1e8);
          });
        });
      }
      
      setPreview({ ...parsed, dsl: correctedDsl });

      if (correctedDsl) {
        try {
          const items = await fetchWorkingPoolByDsl(correctedDsl, currentMarket);
          setMatchedCount(items.length);
          // fetchWorkingPoolByDsl already syncs to backend
          setWorkingPool(items, true); 
        } catch (e) {
          console.warn('Failed to pre-calculate pool size', e);
        }
      }

      if (parsed.mapping?.factors && parsed.mapping?.defaults) {
        const dummyChildren = parsed.mapping.factors
          .filter((f: string) => parsed.mapping.defaults?.[f]?.threshold !== undefined)
          .map((f: string) => {
            const factorDef = FACTORS.find(item => item.key === f);
            const isBillion = factorDef?.unit === '亿';
            const val = parsed.mapping.defaults[f].threshold;
            return {
              type: 'numeric',
              factor: f,
              operator: '>',
              threshold: isBillion ? Math.floor(val * 1e8) : val
            };
          });
        if (dummyChildren.length > 0) {
          setConditions({ type: 'composite', op: 'AND', children: dummyChildren } as any);
        }
      }
      message.success('解析成功');
    } catch (err: any) {
      console.error('parseText failed', err);
      message.error(err?.message || '智能解析失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const runStrategy = async () => {
    // In V2, workingPool should already be populated if analyze was successful
    if (workingPool.length === 0 && !preview.dsl) {
      message.warning('请先完成解析或添加自选股票');
      return;
    }
    setLoading(true);
    try {
      if (preview.dsl) {
        // If there's a DSL but maybe analyze wasn't called or we want to refresh
        const items = await fetchWorkingPoolByDsl(preview.dsl, currentMarket);
        setWorkingPool(items, true);
        message.success(`已生成股票池，包含 ${items.length} 只股票`);
      } else {
        message.success(`当前已选 ${workingPool.length} 只股票`);
      }
      onNext();
    } catch (err: any) {
      console.error('runStrategy failed', err);
      message.error(err?.message || '生成股票池失败');
    } finally {
      setLoading(false);
    }
  };

  const runVisualStrategy = async () => {
    if (!conditions) {
      message.warning('请先添加筛选条件');
      return;
    }
    setLoading(true);
    try {
      const { parseConditions, queryPool } = await import('../services/wizardService');
      const parsed = await parseConditions({ conditions });
      const poolRes = await queryPool({ dsl: parsed.dsl });
      if (!poolRes.items || poolRes.items.length === 0) {
        message.warning('未获取到股票池，请检查条件后重试');
        return;
      }
      const items = (poolRes.items || []).map((x: any) => ({
        symbol: String(x?.symbol || x?.code || '').trim(),
        name: String(x?.name || '').trim(),
        marketCap: Number(x?.metrics?.market_cap ?? x?.market_cap ?? 0) || 0,
        pe: Number(x?.metrics?.pe ?? x?.pe ?? 0) || 0,
        price: Number(x?.metrics?.close ?? x?.price ?? 0) || 0,
      })).filter((x: any) => x.symbol);
      
      setWorkingPool(items);
      message.success(`已生成股票池，包含 ${items.length} 只股票`);
      onNext();
    } catch (err: any) {
      console.error('runVisualStrategy failed', err);
      message.error(err?.message || '生成股票池失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full p-2">
      <div className="mb-8">
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          type="line"
          className="custom-premium-tabs"
          items={[
            {
              key: 'nlp',
              label: (
                <div className="flex items-center gap-2 px-4 py-1">
                  <BulbOutlined />
                  <span className="font-medium">自然语言描述</span>
                </div>
              ),
              children: (
                <div className="mt-3">
                  <Row gutter={24}>
                    <Col span={16}>
                      <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm hover:shadow-md transition-all duration-300">
                        <Title level={5} className="mb-4 text-gray-800 flex items-center gap-2">
                          <SendOutlined className="text-blue-500" />
                          请输入选股逻辑
                        </Title>
                        <TextArea
                          rows={6}
                          placeholder="例如：市值在10-100亿之间且ROE小于30的股票"
                          value={text}
                          onChange={(e) => setText(e.target.value)}
                          className="text-lg p-4 rounded-2xl border-gray-200 focus:border-blue-400 focus:ring-4 focus:ring-blue-50 transition-all"
                          style={{ resize: 'none' }}
                        />
                        
                        <div className="mt-4 mb-6">
                          <div className="flex items-center gap-2 mb-3">
                            <Text type="secondary" className="text-xs font-medium uppercase tracking-wider">快速模版</Text>
                            <div className="h-px flex-1 bg-gray-100" />
                            <Text type="secondary" className="text-[10px]">{visibleTemplates.length} 个</Text>
                          </div>
                          {/* 分类筛选条 */}
                          <div className="flex flex-wrap gap-1.5 mb-3">
                            {['all', ...Object.keys(templateGroups)].map((cat) => (
                              <button
                                key={cat}
                                onClick={() => setTemplateCategory(cat)}
                                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                                  templateCategory === cat
                                    ? 'bg-blue-600 text-white shadow-sm'
                                    : 'bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100'
                                }`}
                              >
                                {cat === 'all' ? '全部' : cat}
                              </button>
                            ))}
                          </div>
                          {/* 模板按钮（最多 250px 高度，可滚动） */}
                          <div
                            className="flex flex-wrap gap-2 overflow-y-auto pr-1"
                            style={{ maxHeight: 250 }}
                          >
                            {visibleTemplates.map((t) => (
                              <button
                                key={`${t.category}-${t.label}`}
                                onClick={() => useTemplate(t.value)}
                                title={t.value}
                                className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200
                                  bg-blue-50 text-blue-600 border border-blue-100 hover:bg-blue-600 hover:text-white hover:border-blue-600
                                  active:scale-95 shadow-sm"
                              >
                                {t.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        <Divider className="my-8" />

                        <div className="flex justify-start items-center">
                          <div className="flex items-center gap-4">
                            <Button 
                              type="primary" 
                              size="large" 
                              onClick={analyze} 
                              loading={loading} 
                              icon={<ThunderboltOutlined />}
                              className="h-12 px-8 rounded-2xl bg-gradient-to-r from-blue-600 to-blue-500 border-none shadow-lg shadow-blue-200 hover:shadow-blue-300 transition-all"
                            >
                              智能解析
                            </Button>
                            <AnimatePresence>
                              {matchedCount !== null && (
                                <motion.div
                                  initial={{ opacity: 0, x: -10 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  className="flex items-center gap-2 text-gray-500"
                                >
                                  <div className="w-2 h-2 rounded-full bg-green-500" />
                                  <span>
                                    匹配到 <span className="text-blue-600 font-bold text-lg">{matchedCount}</span> 只标的
                                  </span>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        </div>
                      </div>
                    </Col>
                    <Col span={8}>
                      <Card
                        variant="borderless"
                        className="h-full rounded-3xl bg-gray-50/50 border border-gray-100 shadow-sm"
                        title={<span className="text-gray-700 font-bold">逻辑预览</span>}
                      >
                        {!preview.dsl ? (
                          <div className="space-y-6 text-gray-500 leading-relaxed text-sm">
                            <div className="p-4 bg-white rounded-2xl border border-gray-100">
                              <p className="font-medium text-gray-700 mb-2">💡 提示</p>
                              <p className="mb-2">您可以直接用自然语言描述您期望的底层股票池。</p>
                              <p className="text-orange-600 font-medium">⚠️ 请注意：建议在此构建宽泛的备选池以保证 AI 的学习空间；若过滤条件过于严格，可能会导致标的过少而影响回测效果。如需在实际交易中精准限定名单，请在后续的策略配置中设置。</p>
                            </div>
                            <p>
                              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;QuantMind 是一款企业级 AI 量化交易平台，基于 Qlib 框架深度定制。我们依托前沿的深度学习模型与海量特征，为您提供专业的每日盘后自动决策服务。
                            </p>
                            <p>
                              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;您无需深谙复杂算法，只需构建期望的股票池与风险偏好，AI 引擎即可随市场行情实时迭代，为您精准预测次日最具潜力的投资组合。
                            </p>
                          </div>
                        ) : (
                          <div className="space-y-6">
                            <Alert 
                              message="解析成功" 
                              type="success" 
                              showIcon 
                              className="rounded-2xl border-emerald-100 bg-emerald-50 text-emerald-800"
                            />
                            <div>
                              <Text strong className="text-xs text-gray-400 uppercase tracking-wider mb-2 block">生成的查询逻辑 (DSL)</Text>
                              <div className="bg-white border border-gray-100 p-4 rounded-2xl font-mono text-xs text-blue-600 break-all leading-relaxed">
                                {preview.dsl}
                              </div>
                            </div>
                            {preview.mapping?.factors && (
                              <div>
                                <Text strong className="text-xs text-gray-400 uppercase tracking-wider mb-2 block">识别因子</Text>
                                <div className="flex flex-wrap gap-2">
                                  {preview.mapping.factors.map((f: string) => (
                                    <Tag key={f} className="m-0 px-3 py-1 rounded-full bg-blue-50 border-blue-100 text-blue-600 font-medium">
                                      {f}
                                    </Tag>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </Card>
                    </Col>
                  </Row>
                </div>
              )
            },
            {
              key: 'visual',
              label: (
                <div className="flex items-center gap-2 px-4 py-1">
                  <EditOutlined />
                  <span className="font-medium">简易构建器</span>
                </div>
              ),
              children: (
                <div className="mt-3 bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
                  <SimpleLogicBuilder onChange={(c) => setConditions(c)} />
                </div>
              )
            },
            {
              key: 'custom',
              label: (
                <div className="flex items-center gap-2 px-4 py-1">
                  <StockOutlined />
                  <span className="font-medium">股票池管理</span>
                </div>
              ),
              children: (
                <div className="mt-3 bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
                  <Alert
                    message="手动添加您关注的特定股票，它们将与筛选结果合并。"
                    type="info"
                    showIcon
                    className="mb-4 rounded-xl py-2 px-4"
                  />
                  <div style={{ height: '550px' }}>
                    <CustomStockSelector />
                  </div>
                </div>
              )
            }
          ]}
        />
      </div>
      
      <style>{`
        .custom-premium-tabs .ant-tabs-nav {
          margin-bottom: 0 !important;
        }
        .custom-premium-tabs .ant-tabs-nav::before {
          display: none !important;
        }
        .custom-premium-tabs .ant-tabs-tab {
          padding: 8px 0 !important;
          margin: 0 4px 0 0 !important;
          border-radius: 12px !important;
          transition: all 0.3s !important;
        }
        .custom-premium-tabs .ant-tabs-tab-active {
          background: #eff6ff !important;
        }
        .custom-premium-tabs .ant-tabs-tab-active .ant-tabs-tab-btn {
          color: #2563eb !important;
        }
        .custom-premium-tabs .ant-tabs-ink-bar {
          display: none !important;
        }
      `}</style>
    </div>
  );
};

export default NaturalTextInput;
