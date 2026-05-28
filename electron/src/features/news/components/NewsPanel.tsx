/**
 * NewsPage — 后台管理 → 资讯源 / 财务事件
 * 三栏自适应布局：
 *   左：Huntly 文件夹 / 订阅源树（可折叠）
 *   中：文章流（弹性宽度）
 *   右：正文（弹性宽度，最小 420，最大 600）
 * 轮询：10s 抓最新一页，HeaderBar 显示 "上次同步：X 秒前"
 * 数据来源: QuantMind 后端 /api/v1/news/* (代理 Huntly)
 */

import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  Badge,
  Button,
  DatePicker,
  Empty,
  Input,
  List,
  Modal,
  Pagination,
  Segmented,
  Select,
  Spin,
  Tag,
  Tooltip,
  Typography,
  Tree,
  message,
} from 'antd';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  BellOutlined,
  FireOutlined,
  GlobalOutlined,
  LeftOutlined,
  LinkOutlined,
  MinusOutlined,
  ReloadOutlined,
  RightOutlined,
  RiseOutlined,
  StarFilled,
  StarOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';
import dayjs, { type Dayjs } from 'dayjs';
import {
  NewsArticle,
  NewsArticleDetail,
  NewsEnrichmentStats,
  NewsFolder,
  NewsHealthInfo,
  NewsSource,
  newsService,
} from '../services/newsService';

const { Text, Title, Paragraph } = Typography;
const { RangePicker } = DatePicker;

const POLL_INTERVAL_MS = 10_000;

type FeedMode = 'all' | 'events' | 'starred';
type SentimentFilter = 'any' | 'bullish' | 'bearish' | 'neutral';
type SelectionKey = 'all' | `folder-${number}` | `source-${number}`;

// A股配色：利好=红, 利空=绿
const COLOR_BULLISH = '#dc2626';   // 红
const COLOR_BEARISH = '#16a34a';   // 绿
const COLOR_NEUTRAL = '#64748b';   // 灰

// 常用市场类型快捷标签 (event_tag)
const QUICK_EVENT_CHIPS = [
  { label: 'A股', value: '市场' },
  { label: '财报', value: '财报' },
  { label: '宏观', value: '宏观' },
  { label: '期货/原油', value: '期货' },
  { label: '外汇', value: '外汇' },
  { label: '加密/区块链', value: '加密' },
];

const formatRelative = (iso?: string | null) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 5) return '刚刚';
  if (diff < 60) return `${Math.floor(diff)}秒前`;
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}天前`;
  return d.toLocaleDateString('zh-CN');
};

export const NewsPanel: React.FC = () => {
  const [health, setHealth] = useState<NewsHealthInfo | null>(null);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [folders, setFolders] = useState<NewsFolder[]>([]);
  const [selection, setSelection] = useState<SelectionKey>('all');
  const [feedMode, setFeedMode] = useState<FeedMode>('all');
  const [keyword, setKeyword] = useState('');

  // enrichment 过滤
  const [sentimentFilter, setSentimentFilter] = useState<SentimentFilter>('any');
  const [industryFilter, setIndustryFilter] = useState<string[]>([]);
  const [tickerFilter, setTickerFilter] = useState<string[]>([]);
  const [eventTagFilter, setEventTagFilter] = useState<string[]>([]);
  const [countryFilter, setCountryFilter] = useState<string[]>([]);
  const [regionFilter, setRegionFilter] = useState<string[]>([]);
  const [keyTermFilter, setKeyTermFilter] = useState<string[]>([]);
  const [dateEntFilter, setDateEntFilter] = useState<string[]>([]);
  const [provinceFilter, setProvinceFilter] = useState<string[]>([]);
  const [cityFilter, setCityFilter] = useState<string[]>([]);
  const [politicianFilter, setPoliticianFilter] = useState<string[]>([]);
  const [visitFilter, setVisitFilter] = useState<string[]>([]);
  const [departmentFilter, setDepartmentFilter] = useState<string[]>([]);
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildingAll, setRebuildingAll] = useState(false);
  const [rebuildProgress, setRebuildProgress] = useState<{
    running: boolean;
    total: number;
    processed: number;
    ok: number;
    failed: number;
    elapsed_seconds?: number;
    eta_seconds?: number | null;
  } | null>(null);
  const rebuildPollRef = useRef<number | null>(null);
  const [strongOnly, setStrongOnly] = useState(false);
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [stats, setStats] = useState<NewsEnrichmentStats | null>(null);

  // 分页
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalArticles, setTotalArticles] = useState(0);

  // 三栏可拖拽布局 (百分比)
  const [leftWidth, setLeftWidth] = useState(20);
  const [midWidth, setMidWidth] = useState(40);
  const dragRef = useRef<{ side: 'left' | 'right'; startX: number; startLeft: number; startMid: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [latestPublishedAt, setLatestPublishedAt] = useState<string | null>(null);
  const [lastSyncTick, setLastSyncTick] = useState<number>(Date.now());

  const [selectedArticleId, setSelectedArticleId] = useState<number | null>(null);
  const [articleDetail, setArticleDetail] = useState<NewsArticleDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>(['all']);
  const [_, forceTick] = useState(0); // 强制时间标签 1s 重渲染
  const pollTimer = useRef<number | null>(null);

  // —— 数据拉取 ——
  const checkHealth = useCallback(async () => {
    try {
      setHealth(await newsService.health());
    } catch {
      setHealth({ huntly_status: 'unreachable', huntly_base_url: '?' });
    }
  }, []);

  const loadSources = useCallback(async () => {
    try {
      const { sources, folders } = await newsService.listSources();
      setSources(sources);
      setFolders(folders);
    } catch {
      setSources([]);
      setFolders([]);
    }
  }, []);

  const loadArticles = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {
        keyword: keyword || undefined,
        only_financial_event: feedMode === 'events',
        page: currentPage,
        page_size: pageSize,
      };
      if (selection.startsWith('source-')) {
        params.source_id = Number(selection.slice('source-'.length));
      } else if (selection.startsWith('folder-')) {
        params.folder_id = Number(selection.slice('folder-'.length));
      }
      if (sentimentFilter !== 'any') params.sentiment = sentimentFilter;
      if (industryFilter.length) params.industries = industryFilter.join(',');
      if (tickerFilter.length) params.tickers = tickerFilter.join(',');
      if (eventTagFilter.length) params.event_tags = eventTagFilter.join(',');
      if (countryFilter.length) params.countries = countryFilter.join(',');
      if (regionFilter.length) params.regions = regionFilter.join(',');
      if (keyTermFilter.length) params.key_terms = keyTermFilter.join(',');
      if (dateEntFilter.length) params.date_entities = dateEntFilter.join(',');
      if (provinceFilter.length) params.provinces = provinceFilter.join(',');
      if (cityFilter.length) params.cities = cityFilter.join(',');
      if (politicianFilter.length) params.politicians = politicianFilter.join(',');
      if (visitFilter.length) params.visits = visitFilter.join(',');
      if (departmentFilter.length) params.departments = departmentFilter.join(',');
      if (strongOnly) params.strong_only = true;
      if (dateRange?.[0]) params.since = dateRange[0].startOf('day').toISOString();
      if (dateRange?.[1]) params.until = dateRange[1].endOf('day').toISOString();
      const r = await newsService.listArticles(params);
      let list = r.articles ?? [];
      if (feedMode === 'starred') list = list.filter((a) => a.starred);
      setArticles(list);
      setTotalArticles(r.total ?? list.length);
      setLatestPublishedAt(r.latest_published_at ?? null);
      setLastSyncTick(Date.now());
    } catch {
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [selection, keyword, feedMode, sentimentFilter, industryFilter, tickerFilter, eventTagFilter, countryFilter, regionFilter, keyTermFilter, dateEntFilter, provinceFilter, cityFilter, politicianFilter, visitFilter, departmentFilter, strongOnly, dateRange, currentPage, pageSize]);

  const loadStats = useCallback(async () => {
    try {
      const params: any = {};
      if (sentimentFilter !== 'any') params.sentiment = sentimentFilter;
      if (industryFilter.length) params.industries = industryFilter.join(',');
      if (tickerFilter.length) params.tickers = tickerFilter.join(',');
      if (eventTagFilter.length) params.event_tags = eventTagFilter.join(',');
      if (countryFilter.length) params.countries = countryFilter.join(',');
      if (regionFilter.length) params.regions = regionFilter.join(',');
      if (keyTermFilter.length) params.key_terms = keyTermFilter.join(',');
      if (dateEntFilter.length) params.date_entities = dateEntFilter.join(',');
      if (provinceFilter.length) params.provinces = provinceFilter.join(',');
      if (cityFilter.length) params.cities = cityFilter.join(',');
      if (politicianFilter.length) params.politicians = politicianFilter.join(',');
      if (visitFilter.length) params.visits = visitFilter.join(',');
      if (departmentFilter.length) params.departments = departmentFilter.join(',');
      if (strongOnly) params.strong_only = true;
      if (keyword?.trim()) params.keyword = keyword.trim();
      const s = await newsService.enrichmentStats(params);
      setStats(s);
    } catch {
      setStats(null);
    }
  }, [sentimentFilter, industryFilter, tickerFilter, eventTagFilter, countryFilter, regionFilter, keyTermFilter, dateEntFilter, provinceFilter, cityFilter, politicianFilter, visitFilter, departmentFilter, strongOnly, keyword]);

  const handleRebuildTags = useCallback(async () => {
    Modal.confirm({
      title: '重建标签',
      content: '将对未 enrichment 的文章重新提取标签（股票/行业/情感/省份/城市/领导人/调研等），数据量大时可能需要较长时间。确认继续？',
      okText: '开始重建',
      cancelText: '取消',
      onOk: async () => {
        setRebuilding(true);
        try {
          const r = await newsService.runEnrichmentNow(2000);
          message.success({ content: `标签重建完成: ${r.written} 篇已更新`, key: 'rebuild-tags', duration: 3 });
          await loadArticles();
          await loadStats();
        } catch {
          message.error({ content: '标签重建失败', key: 'rebuild-tags' });
        } finally {
          setRebuilding(false);
        }
      },
    });
  }, [loadArticles, loadStats]);

  const stopRebuildPolling = useCallback(() => {
    if (rebuildPollRef.current) {
      window.clearInterval(rebuildPollRef.current);
      rebuildPollRef.current = null;
    }
  }, []);

  const startRebuildPolling = useCallback(() => {
    stopRebuildPolling();
    rebuildPollRef.current = window.setInterval(async () => {
      try {
        const p = await newsService.getRebuildProgress();
        setRebuildProgress(p);
        if (!p.running) {
          stopRebuildPolling();
          setRebuildingAll(false);
          message.success({
            content: `全量重建完成: 共 ${p.total} 篇 / 成功 ${p.ok} / 失败 ${p.failed} (${(p.elapsed_seconds / 60).toFixed(1)} 分钟)`,
            key: 'rebuild-all',
            duration: 6,
          });
          await loadArticles();
          await loadStats();
        }
      } catch {
        // ignore single tick error
      }
    }, 3000);
  }, [stopRebuildPolling, loadArticles, loadStats]);

  const handleRebuildAll = useCallback(() => {
    Modal.confirm({
      title: '一键重建全部标签',
      width: 480,
      content: (
        <div>
          <p>将直接读取 Huntly 数据库, 对 <b>全部 8 万多篇</b> 文章<b style={{ color: '#ef4444' }}>强制重建</b>标签 (覆盖已有 enrichment)。</p>
          <p style={{ color: '#94a3b8', fontSize: 12 }}>
            后台异步运行, 可关闭此对话框。预计耗时 30 ~ 90 分钟, 期间可继续浏览/筛选 (新数据会陆续生效)。
          </p>
          <p style={{ color: '#94a3b8', fontSize: 12 }}>
            适用场景: 词典/模型升级后想让所有历史文章按新规则重新打标签。
          </p>
        </div>
      ),
      okText: '开始强制重建',
      cancelText: '取消',
      okButtonProps: { type: 'primary', danger: true },
      onOk: async () => {
        setRebuildingAll(true);
        try {
          const r = await newsService.rebuildAllEnrichment(true);
          if (r.started) {
            message.success({ content: `已启动后台强制重建任务 (共 ${r.total || '?'} 篇)`, key: 'rebuild-all' });
          } else {
            message.info({ content: `任务已在运行中 (${r.processed}/${r.total})`, key: 'rebuild-all' });
          }
          setRebuildProgress(r as any);
          startRebuildPolling();
        } catch {
          setRebuildingAll(false);
          message.error({ content: '启动全量重建失败', key: 'rebuild-all' });
        }
      },
    });
  }, [startRebuildPolling]);

  useEffect(() => {
    checkHealth();
    loadSources();
    loadStats();
    // 页面打开时若后端还在跑全量重建, 自动接上进度
    (async () => {
      try {
        const p = await newsService.getRebuildProgress();
        if (p.running) {
          setRebuildProgress(p);
          setRebuildingAll(true);
          startRebuildPolling();
        } else if (p.total > 0) {
          setRebuildProgress(p);
        }
      } catch { /* ignore */ }
    })();
    return () => {
      if (rebuildPollRef.current) window.clearInterval(rebuildPollRef.current);
    };
  }, [checkHealth, loadSources, loadStats, startRebuildPolling]);

  useEffect(() => {
    loadArticles();
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = window.setInterval(() => {
      loadArticles();
      loadSources();
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    };
  }, [loadArticles, loadSources]);

  // 筛选条件变化时重置到第 1 页
  useEffect(() => {
    setCurrentPage(1);
  }, [selection, keyword, feedMode, sentimentFilter, industryFilter, tickerFilter, eventTagFilter, countryFilter, regionFilter, keyTermFilter, dateEntFilter, provinceFilter, cityFilter, politicianFilter, visitFilter, departmentFilter, strongOnly, dateRange]);

  // 拖拽分隔条：mousemove / mouseup
  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragRef.current || !containerRef.current) return;
      e.preventDefault();
      const rect = containerRef.current.getBoundingClientRect();
      const totalW = rect.width;
      const dx = e.clientX - dragRef.current.startX;
      const dPct = (dx / totalW) * 100;
      const minPct = 10; // 最小 10%
      if (dragRef.current.side === 'left') {
        const newLeft = Math.max(minPct, Math.min(50, dragRef.current.startLeft + dPct));
        setLeftWidth(newLeft);
      } else {
        const newMid = Math.max(20, Math.min(60, dragRef.current.startMid + dPct));
        setMidWidth(newMid);
      }
    };
    const onMouseUp = () => {
      dragRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  // 标签统计单独低频刷新（60s），避免拖累主轮询
  useEffect(() => {
    const t = window.setInterval(loadStats, 60_000);
    return () => window.clearInterval(t);
  }, [loadStats]);

  // 1s tick for relative-time labels
  useEffect(() => {
    const t = window.setInterval(() => forceTick((x) => x + 1), 1000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    if (selectedArticleId == null) {
      setArticleDetail(null);
      return;
    }
    setDetailLoading(true);
    newsService
      .getArticle(selectedArticleId)
      .then((d) => {
        setArticleDetail(d);
        if (!d.read) newsService.markRead(selectedArticleId, true).catch(() => undefined);
      })
      .catch(() => setArticleDetail(null))
      .finally(() => setDetailLoading(false));
  }, [selectedArticleId]);

  // —— 派生数据 ——
  const totalUnread = useMemo(
    () => sources.reduce((acc, s) => acc + (s.unread_count || 0), 0),
    [sources],
  );

  const treeData: DataNode[] = useMemo(() => {
    const allUnread = totalUnread;
    const folderMap = new Map<number, NewsSource[]>();
    sources.forEach((s) => {
      const fid = s.folder_id ?? 0;
      if (!folderMap.has(fid)) folderMap.set(fid, []);
      folderMap.get(fid)!.push(s);
    });
    const folderNodes: DataNode[] = folders.map((f) => {
      const items = folderMap.get(f.folder_id) || [];
      return {
        key: `folder-${f.folder_id}`,
        title: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>
              {f.folder_name || '未分组'}
            </span>
            <Text type="secondary" style={{ fontSize: 10 }}>{items.length}</Text>
            {f.unread_count > 0 && <Badge count={f.unread_count} size="small" />}
          </div>
        ),
        children: items.map((s) => ({
          key: `source-${s.source_id}`,
          title: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                {s.source_name}
              </span>
              {(s.unread_count ?? 0) > 0 && <Badge count={s.unread_count} size="small" />}
            </div>
          ),
          isLeaf: true,
        })),
      };
    });
    return [
      {
        key: 'all',
        title: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ flex: 1, fontWeight: 600 }}>全部</span>
            {allUnread > 0 && <Badge count={allUnread} size="small" style={{ backgroundColor: '#6366f1' }} />}
          </div>
        ),
        isLeaf: true,
      },
      ...folderNodes,
    ];
  }, [sources, folders, totalUnread]);

  // —— 默认展开所有 folder ——
  useEffect(() => {
    if (folders.length > 0 && expandedKeys.length <= 1) {
      setExpandedKeys(['all', ...folders.map((f) => `folder-${f.folder_id}`)]);
    }
  }, [folders]);

  const handleStar = useCallback(async (article: NewsArticle, ev: React.MouseEvent) => {
    ev.stopPropagation();
    const next = !article.starred;
    try {
      await newsService.toggleStar(article.id, next);
      setArticles((prev) => prev.map((a) => (a.id === article.id ? { ...a, starred: next } : a)));
      if (selectedArticleId === article.id && articleDetail) {
        setArticleDetail({ ...articleDetail, starred: next });
      }
    } catch {
      message.error('操作失败');
    }
  }, [selectedArticleId, articleDetail]);

  const handleRefreshAll = useCallback(async () => {
    message.loading({ content: '正在抓取最新资讯...', key: 'news-refresh', duration: 0 });
    try {
      // 简单触发：刷新文章列表 + 来源列表
      await Promise.all([loadArticles(), loadSources()]);
      message.success({ content: '已刷新', key: 'news-refresh' });
    } catch {
      message.error({ content: '刷新失败', key: 'news-refresh' });
    }
  }, [loadArticles, loadSources]);

  // —— 渲染 ——
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        minHeight: 0,
        background: '#ffffff',
        overflow: 'hidden',
        // 底部留出 84px 给 FloatingNavBar (位于 bottom:14px, 约 56px 高 + 14px 间距)
        paddingBottom: 84,
        boxSizing: 'border-box',
      }}
    >
      {/* 顶部工具栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '14px 20px',
          gap: 14,
          borderBottom: '1px solid #e2e8f0',
          background: 'linear-gradient(180deg, #fafbff 0%, #f8fafc 100%)',
          flexWrap: 'wrap',
        }}
      >
        <BellOutlined style={{ color: '#6366f1', fontSize: 20 }} />
        <Title level={5} style={{ margin: 0, fontSize: 16 }}>
          资讯监控
        </Title>
        <Tag color={health?.huntly_status === 'up' ? 'green' : 'red'} style={{ margin: 0 }}>
          {health?.huntly_status === 'up' ? 'Huntly 已连接' : '未连接'}
        </Tag>
        <Tooltip title={latestPublishedAt ? `最新一条发布于 ${new Date(latestPublishedAt).toLocaleString('zh-CN')}` : '暂无文章'}>
          <Tag icon={<SyncOutlined spin={loading} />} color="processing" style={{ margin: 0 }}>
            最新：{formatRelative(latestPublishedAt)}
          </Tag>
        </Tooltip>
        <Tooltip title={`上次轮询：${new Date(lastSyncTick).toLocaleTimeString('zh-CN')}（每 ${POLL_INTERVAL_MS / 1000}s 自动）`}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            同步 {formatRelative(new Date(lastSyncTick).toISOString())}
          </Text>
        </Tooltip>
        <Badge count={totalUnread} overflowCount={9999} style={{ backgroundColor: '#6366f1' }} />

        <Segmented
          size="small"
          value={feedMode}
          onChange={(v) => setFeedMode(v as FeedMode)}
          options={[
            { label: <span><GlobalOutlined /> 全部</span>, value: 'all' },
            { label: <span><ThunderboltOutlined /> 财务事件</span>, value: 'events' },
            { label: <span><FireOutlined /> 收藏</span>, value: 'starred' },
          ]}
          style={{ marginLeft: 8 }}
        />
        <Input.Search
          allowClear
          size="small"
          placeholder="搜索: 标题/内容/股票代码/行业/标签..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onSearch={() => loadArticles()}
          style={{ width: 320 }}
        />
        <div style={{ flex: 1 }} />
        <Tooltip title="立即刷新">
          <Button
            size="small"
            type="primary"
            ghost
            icon={<ReloadOutlined spin={loading} />}
            onClick={handleRefreshAll}
          >
            刷新
          </Button>
        </Tooltip>
        <Tooltip title="重新提取所有文章的标签（股票/行业/情感/省份/城市/领导人/调研等）">
          <Button
            size="small"
            ghost
            danger
            icon={<SyncOutlined spin={rebuilding} />}
            loading={rebuilding}
            onClick={handleRebuildTags}
          >
            重建标签
          </Button>
        </Tooltip>
        <Tooltip title="一键对全部 8 万多篇历史文章重建标签 (后台异步)">
          <Button
            size="small"
            type="primary"
            danger
            ghost
            icon={<SyncOutlined spin={rebuildingAll} />}
            loading={rebuildingAll}
            onClick={handleRebuildAll}
          >
            {rebuildingAll && rebuildProgress && rebuildProgress.total > 0
              ? `重建中 ${rebuildProgress.processed}/${rebuildProgress.total}`
              : '一键重建全部'}
          </Button>
        </Tooltip>
        {health?.huntly_base_url && (
          <Tooltip title="打开 Huntly 后台管理订阅源">
            <a
              href={health.huntly_base_url.replace('http://quantmind-huntly', `http://${window.location.hostname}:8090`)}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: 12, color: '#6366f1', whiteSpace: 'nowrap' }}
            >
              <LinkOutlined /> Huntly 后台
            </a>
          </Tooltip>
        )}
      </div>

      {/* 第二排：金融过滤器（情感 / 行业 / 股票 / 事件 / 时间 / 强信号） */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '8px 20px',
          gap: 10,
          borderBottom: '1px solid #e2e8f0',
          background: '#ffffff',
          flexWrap: 'wrap',
          fontSize: 12,
        }}
      >
        <Text type="secondary" style={{ fontSize: 12 }}>情感:</Text>
        <Segmented
          size="small"
          value={sentimentFilter}
          onChange={(v) => setSentimentFilter(v as SentimentFilter)}
          options={[
            { label: <span>全部</span>, value: 'any' },
            { label: <span style={{ color: COLOR_BULLISH }}><RiseOutlined /> 利好</span>, value: 'bullish' },
            { label: <span style={{ color: COLOR_BEARISH }}><ArrowDownOutlined /> 利空</span>, value: 'bearish' },
            { label: <span style={{ color: COLOR_NEUTRAL }}><MinusOutlined /> 中性</span>, value: 'neutral' },
          ]}
        />
        <Tooltip title="只显示强信号: |情感分|>=0.5">
          <Button
            size="small"
            type={strongOnly ? 'primary' : 'default'}
            danger={strongOnly}
            icon={<FireOutlined />}
            onClick={() => setStrongOnly((x) => !x)}
          >
            强信号
          </Button>
        </Tooltip>
        <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>时间:</Text>
        <Segmented
          size="small"
          value={(() => {
            if (!dateRange?.[0]) return 'all';
            const since = dateRange[0];
            const today = dayjs().startOf('day');
            if (since.isSame(today)) return '1d';
            if (since.isSame(today.subtract(2, 'day'))) return '3d';
            if (since.isSame(today.subtract(6, 'day'))) return '7d';
            if (since.isSame(today.subtract(29, 'day'))) return '30d';
            return 'custom';
          })()}
          onChange={(v) => {
            const today = dayjs().endOf('day');
            switch (v) {
              case 'all': setDateRange(null); break;
              case '1d': setDateRange([dayjs().startOf('day'), today]); break;
              case '3d': setDateRange([dayjs().subtract(2, 'day').startOf('day'), today]); break;
              case '7d': setDateRange([dayjs().subtract(6, 'day').startOf('day'), today]); break;
              case '30d': setDateRange([dayjs().subtract(29, 'day').startOf('day'), today]); break;
            }
          }}
          options={[
            { label: '不限', value: 'all' },
            { label: '今日', value: '1d' },
            { label: '近3日', value: '3d' },
            { label: '近7日', value: '7d' },
            { label: '近30日', value: '30d' },
          ]}
        />
        <RangePicker
          size="small"
          value={dateRange as any}
          onChange={(v) => setDateRange(v as any)}
          allowClear
          style={{ width: 240 }}
        />
        <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>行业:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="按行业筛选"
          value={industryFilter}
          onChange={setIndustryFilter}
          options={(stats?.top_industries ?? []).map((i) => ({
            value: i.name,
            label: `${i.name} (${i.count})`,
          }))}
          style={{ minWidth: 200, maxWidth: 320 }}
          maxTagCount="responsive"
        />
        <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>股票:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="按股票筛选"
          value={tickerFilter}
          onChange={setTickerFilter}
          options={(stats?.top_tickers ?? []).map((t) => ({
            value: t.ticker,
            label: `${t.name ? t.name + ' ' : ''}${t.ticker} (${t.count})`,
          }))}
          style={{ minWidth: 200, maxWidth: 320 }}
          maxTagCount="responsive"
          showSearch
          filterOption={(input, opt) =>
            String(opt?.label || '').toLowerCase().includes(input.toLowerCase())
          }
        />
        {(sentimentFilter !== 'any' || industryFilter.length > 0 || tickerFilter.length > 0 || eventTagFilter.length > 0 || countryFilter.length > 0 || regionFilter.length > 0 || keyTermFilter.length > 0 || dateEntFilter.length > 0 || provinceFilter.length > 0 || cityFilter.length > 0 || politicianFilter.length > 0 || visitFilter.length > 0 || departmentFilter.length > 0 || strongOnly || dateRange) && (
          <Button
            type="link"
            size="small"
            onClick={() => {
              setSentimentFilter('any');
              setIndustryFilter([]);
              setTickerFilter([]);
              setEventTagFilter([]);
              setCountryFilter([]);
              setRegionFilter([]);
              setKeyTermFilter([]);
              setDateEntFilter([]);
              setProvinceFilter([]);
              setCityFilter([]);
              setPoliticianFilter([]);
              setVisitFilter([]);
              setDepartmentFilter([]);
              setStrongOnly(false);
              setDateRange(null);
            }}
          >
            清除筛选
          </Button>
        )}
        <div style={{ flex: 1 }} />
        {stats?.sentiment_counts && (() => {
          const filtered = (
            sentimentFilter !== 'any' || industryFilter.length > 0 || tickerFilter.length > 0 ||
            eventTagFilter.length > 0 || countryFilter.length > 0 || regionFilter.length > 0 ||
            keyTermFilter.length > 0 || dateEntFilter.length > 0 ||
            provinceFilter.length > 0 || cityFilter.length > 0 ||
            politicianFilter.length > 0 || visitFilter.length > 0 ||
            departmentFilter.length > 0 ||
            strongOnly || !!keyword?.trim()
          );
          const total = (stats.sentiment_counts.bullish || 0) + (stats.sentiment_counts.bearish || 0) + (stats.sentiment_counts.neutral || 0);
          return (
            <Tooltip title={filtered ? `当前筛选条件下: 共 ${total} 篇文章 (红=利好 / 绿=利空 A股配色)` : '全部 enrich 文章的情感分布'}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {filtered && <Text type="warning" style={{ fontSize: 11, marginRight: 4 }}>筛选后</Text>}
                <span style={{ color: COLOR_BULLISH }}>利好 {stats.sentiment_counts.bullish || 0}</span>
                {' · '}
                <span style={{ color: COLOR_BEARISH }}>利空 {stats.sentiment_counts.bearish || 0}</span>
                {' · '}
                <span style={{ color: COLOR_NEUTRAL }}>中性 {stats.sentiment_counts.neutral || 0}</span>
              </Text>
            </Tooltip>
          );
        })()}
      </div>

      {/* 第三排：常用市场快捷标签 (多选 toggle) */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '6px 20px',
          gap: 8,
          borderBottom: '1px solid #f1f5f9',
          background: '#fafbff',
          flexWrap: 'wrap',
          fontSize: 12,
        }}
      >
        <Text type="secondary" style={{ fontSize: 11 }}>板块:</Text>
        {QUICK_EVENT_CHIPS.map((chip) => {
          const active = eventTagFilter.includes(chip.value);
          return (
            <Tag.CheckableTag
              key={chip.value}
              checked={active}
              onChange={(c) => {
                setEventTagFilter((cur) =>
                  c ? [...cur, chip.value] : cur.filter((x) => x !== chip.value),
                );
              }}
              style={{ fontSize: 11, padding: '2px 10px', borderRadius: 12 }}
            >
              {chip.label}
            </Tag.CheckableTag>
          );
        })}
        {/* 来自 stats 的高频事件 (Top 8, 排除已在 QUICK_EVENT_CHIPS 里的) */}
        {(stats?.top_events ?? []).slice(0, 12)
          .filter((e) => !QUICK_EVENT_CHIPS.some((q) => q.value === e.name))
          .slice(0, 8)
          .map((e) => {
            const active = eventTagFilter.includes(e.name);
            return (
              <Tag.CheckableTag
                key={`auto-${e.name}`}
                checked={active}
                onChange={(c) => {
                  setEventTagFilter((cur) =>
                    c ? [...cur, e.name] : cur.filter((x) => x !== e.name),
                  );
                }}
                style={{ fontSize: 11, padding: '2px 10px', borderRadius: 12 }}
              >
                {e.name} <span style={{ opacity: 0.6 }}>({e.count})</span>
              </Tag.CheckableTag>
            );
          })}
      </div>

      {/* 第四排：地理 / 政情 / 关键词 / 部门 筛选（合并为一行） */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '6px 20px',
          gap: 8,
          borderBottom: '1px solid #f1f5f9',
          background: '#fafbff',
          flexWrap: 'wrap',
          fontSize: 12,
        }}
      >
        <Text type="secondary" style={{ fontSize: 11 }}>国家:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="国家"
          value={countryFilter}
          onChange={setCountryFilter}
          options={(stats?.top_countries ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 120, maxWidth: 200 }}
          maxTagCount="responsive"
        />
        <Text type="secondary" style={{ fontSize: 11 }}>地区:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="地区"
          value={regionFilter}
          onChange={setRegionFilter}
          options={(stats?.top_regions ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 120, maxWidth: 200 }}
          maxTagCount="responsive"
        />
        <Text type="secondary" style={{ fontSize: 11 }}>省份:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="省份"
          value={provinceFilter}
          onChange={setProvinceFilter}
          options={(stats?.top_provinces ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 120, maxWidth: 200 }}
          maxTagCount="responsive"
          showSearch
          filterOption={(input, opt) =>
            String(opt?.label || '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <Text type="secondary" style={{ fontSize: 11 }}>城市:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="城市"
          value={cityFilter}
          onChange={setCityFilter}
          options={(stats?.top_cities ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 120, maxWidth: 200 }}
          maxTagCount="responsive"
          showSearch
          filterOption={(input, opt) =>
            String(opt?.label || '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <Text type="secondary" style={{ fontSize: 11 }}>领导人:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="政治人物"
          value={politicianFilter}
          onChange={setPoliticianFilter}
          options={(stats?.top_politicians ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 120, maxWidth: 200 }}
          maxTagCount="responsive"
          showSearch
          filterOption={(input, opt) =>
            String(opt?.label || '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <Text type="secondary" style={{ fontSize: 11 }}>调研:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="调研/视察"
          value={visitFilter}
          onChange={setVisitFilter}
          options={(stats?.top_visits ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 120, maxWidth: 200 }}
          maxTagCount="responsive"
        />
        <Text type="secondary" style={{ fontSize: 11 }}>部门:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="国家部门"
          value={departmentFilter}
          onChange={setDepartmentFilter}
          options={(stats?.top_departments ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 120, maxWidth: 200 }}
          maxTagCount="responsive"
        />
        <Text type="secondary" style={{ fontSize: 11 }}>关键词:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="产业/政策/外汇..."
          value={keyTermFilter}
          onChange={setKeyTermFilter}
          options={(stats?.top_key_terms ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 160, maxWidth: 280 }}
          maxTagCount="responsive"
          showSearch
          filterOption={(input, opt) =>
            String(opt?.label || '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <Text type="secondary" style={{ fontSize: 11 }}>日期:</Text>
        <Select
          mode="multiple"
          allowClear
          size="small"
          placeholder="日期"
          value={dateEntFilter}
          onChange={setDateEntFilter}
          options={(stats?.top_dates ?? []).map((c) => ({
            value: c.name,
            label: `${c.name} (${c.count})`,
          }))}
          style={{ minWidth: 140, maxWidth: 240 }}
          maxTagCount="responsive"
          showSearch
          filterOption={(input, opt) =>
            String(opt?.label || '').toLowerCase().includes(input.toLowerCase())
          }
        />
      </div>

      {/* 主体三栏 - 可拖拽布局 */}
      <div ref={containerRef} style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {/* 左：文件夹 / 订阅源树 */}
        <div
          style={{
            flex: `0 0 ${leftWidth}%`,
            overflowY: 'auto',
            padding: '8px 6px',
            background: '#fafafa',
          }}
        >
          {treeData.length <= 1 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={<span style={{ color: '#64748b', fontSize: 12 }}>无订阅源</span>}
              style={{ marginTop: 60 }}
            />
          ) : (
            <Tree
              blockNode
              treeData={treeData}
              selectedKeys={[selection]}
              expandedKeys={expandedKeys}
              expandAction="doubleClick"
              onExpand={(keys) => setExpandedKeys(keys)}
              onSelect={(keys, info) => {
                // 点击同一节点 antd 会清空 selectedKeys，这里取被点击节点的 key 保证选中
                const clicked = (info?.node as any)?.key as SelectionKey | undefined;
                const next = (keys[0] as SelectionKey) || clicked;
                if (!next) return;
                setSelection(next);
              }}
              style={{ background: 'transparent', fontSize: 13 }}
            />
          )}
        </div>

        {/* 拖拽分隔条：左-中 */}
        <div
          style={{ flex: '0 0 6px', cursor: 'col-resize', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onMouseDown={(e) => {
            e.preventDefault();
            dragRef.current = { side: 'left', startX: e.clientX, startLeft: leftWidth, startMid: midWidth };
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
          }}
        >
          <div style={{ width: 2, height: 32, background: '#cbd5e1', borderRadius: 1 }} />
        </div>

        {/* 中：文章流 */}
        <div
          style={{
            flex: `0 0 ${midWidth}%`,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {loading && articles.length === 0 ? (
            <div style={{ padding: 80, textAlign: 'center' }}><Spin /></div>
          ) : articles.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span style={{ color: '#64748b', fontSize: 13 }}>
                  {health?.huntly_status === 'up'
                    ? '当前筛选无文章 · 试试 "清除筛选" 或在 Huntly 后台添加 RSS / Twitter 订阅 (Twitter 可用 RSSHub: https://rsshub.app/twitter/user/<用户名>)'
                    : `资讯服务未连接 (${health?.huntly_base_url || ''})`}
                </span>
              }
              style={{ marginTop: 80 }}
            />
          ) : (
            <>
            <div style={{ flex: 1, overflowY: 'auto' }}>
            <List
              size="small"
              dataSource={articles}
              renderItem={(a) => {
                const active = selectedArticleId === a.id;
                return (
                  <List.Item
                    style={{
                      padding: '8px 12px',
                      cursor: 'pointer',
                      background: active ? 'rgba(99,102,241,0.08)' : 'transparent',
                      borderBottom: '1px solid #f1f5f9',
                      borderLeft: active ? '3px solid #6366f1' : '3px solid transparent',
                      opacity: a.read && !active ? 0.7 : 1,
                    }}
                    onClick={() => setSelectedArticleId(a.id)}
                  >
                    <div style={{ width: '100%' }}>
                      <div style={{ display: 'flex', alignItems: 'start', gap: 10 }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                            {a.is_financial_event && (
                              <Tag color="gold" style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px' }}>
                                <ThunderboltOutlined /> 事件
                              </Tag>
                            )}
                            {a.enrichment?.sentiment_label === 'bullish' && (
                              <Tag
                                color="red"
                                style={{
                                  margin: 0,
                                  fontSize: 10,
                                  padding: '0 4px',
                                  lineHeight: '15px',
                                  fontWeight: (a.enrichment.sentiment_score ?? 0) >= 0.5 ? 700 : 500,
                                }}
                              >
                                {(a.enrichment.sentiment_score ?? 0) >= 0.5 ? <FireOutlined /> : <RiseOutlined />} 利好
                                {a.enrichment.sentiment_score != null && ` ${a.enrichment.sentiment_score.toFixed(2)}`}
                              </Tag>
                            )}
                            {a.enrichment?.sentiment_label === 'bearish' && (
                              <Tag
                                color="green"
                                style={{
                                  margin: 0,
                                  fontSize: 10,
                                  padding: '0 4px',
                                  lineHeight: '15px',
                                  fontWeight: (a.enrichment.sentiment_score ?? 0) <= -0.5 ? 700 : 500,
                                }}
                              >
                                {(a.enrichment.sentiment_score ?? 0) <= -0.5 ? <FireOutlined /> : <ArrowDownOutlined />} 利空
                                {a.enrichment.sentiment_score != null && ` ${a.enrichment.sentiment_score.toFixed(2)}`}
                              </Tag>
                            )}
                            <Text style={{ fontSize: 13, fontWeight: a.read ? 400 : 600, lineHeight: 1.4 }}>
                              {a.title}
                            </Text>
                          </div>
                          {a.summary && (
                            <Text style={{ color: '#64748b', fontSize: 11, display: 'block', lineHeight: 1.5 }}>
                              {a.summary.length > 120 ? `${a.summary.slice(0, 120)}...` : a.summary}
                            </Text>
                          )}
                          {/* 标签行：股票 + 行业 + 事件 + 国家 + 地区 + 关键词 + 省份 + 城市 + 领导人 + 调研 */}
                          {(a.enrichment && (
                            a.enrichment.tickers.length > 0 ||
                            a.enrichment.industries.length > 0 ||
                            a.enrichment.event_tags.length > 0 ||
                            (a.enrichment.countries?.length ?? 0) > 0 ||
                            (a.enrichment.regions?.length ?? 0) > 0 ||
                            (a.enrichment.key_terms?.length ?? 0) > 0 ||
                            (a.enrichment.provinces?.length ?? 0) > 0 ||
                            (a.enrichment.cities?.length ?? 0) > 0 ||
                            (a.enrichment.politicians?.length ?? 0) > 0 ||
                            (a.enrichment.visits?.length ?? 0) > 0 ||
                            (a.enrichment.departments?.length ?? 0) > 0
                          )) && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 4 }}>
                              {a.enrichment.tickers.slice(0, 5).map((t) => (
                                <Tag
                                  key={`tk-${t}`}
                                  color="blue"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setTickerFilter((cur) => cur.includes(t) ? cur : [...cur, t]);
                                  }}
                                >
                                  {t}
                                </Tag>
                              ))}
                              {a.enrichment.industries.slice(0, 3).map((ind) => (
                                <Tag
                                  key={`ind-${ind}`}
                                  color="geekblue"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setIndustryFilter((cur) => cur.includes(ind) ? cur : [...cur, ind]);
                                  }}
                                >
                                  {ind.length > 10 ? `${ind.slice(0, 10)}...` : ind}
                                </Tag>
                              ))}
                              {(a.enrichment.countries ?? []).slice(0, 3).map((co) => (
                                <Tag
                                  key={`co-${co}`}
                                  color="purple"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setCountryFilter((cur) => cur.includes(co) ? cur : [...cur, co]);
                                  }}
                                >
                                  {co}
                                </Tag>
                              ))}
                              {(a.enrichment.regions ?? []).slice(0, 2).map((rg) => (
                                <Tag
                                  key={`rg-${rg}`}
                                  color="cyan"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setRegionFilter((cur) => cur.includes(rg) ? cur : [...cur, rg]);
                                  }}
                                >
                                  {rg}
                                </Tag>
                              ))}
                              {a.enrichment.event_tags.slice(0, 3).map((ev) => (
                                <Tag
                                  key={`ev-${ev}`}
                                  color="orange"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setEventTagFilter((cur) => cur.includes(ev) ? cur : [...cur, ev]);
                                  }}
                                >
                                  {ev}
                                </Tag>
                              ))}
                              {(a.enrichment.key_terms ?? []).slice(0, 4).map((kt) => (
                                <Tag
                                  key={`kt-${kt}`}
                                  color="magenta"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setKeyTermFilter((cur) => cur.includes(kt) ? cur : [...cur, kt]);
                                  }}
                                >
                                  {kt}
                                </Tag>
                              ))}
                              {(a.enrichment.provinces ?? []).slice(0, 2).map((pv) => (
                                <Tag
                                  key={`pv-${pv}`}
                                  color="volcano"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setProvinceFilter((cur) => cur.includes(pv) ? cur : [...cur, pv]);
                                  }}
                                >
                                  {pv}
                                </Tag>
                              ))}
                              {(a.enrichment.cities ?? []).slice(0, 2).map((ct) => (
                                <Tag
                                  key={`ct-${ct}`}
                                  color="gold"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setCityFilter((cur) => cur.includes(ct) ? cur : [...cur, ct]);
                                  }}
                                >
                                  {ct}
                                </Tag>
                              ))}
                              {(a.enrichment.politicians ?? []).slice(0, 2).map((pl) => (
                                <Tag
                                  key={`pl-${pl}`}
                                  color="red"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setPoliticianFilter((cur) => cur.includes(pl) ? cur : [...cur, pl]);
                                  }}
                                >
                                  {pl}
                                </Tag>
                              ))}
                              {(a.enrichment.visits ?? []).slice(0, 1).map((vs) => (
                                <Tag
                                  key={`vs-${vs}`}
                                  color="lime"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setVisitFilter((cur) => cur.includes(vs) ? cur : [...cur, vs]);
                                  }}
                                >
                                  {vs}
                                </Tag>
                              ))}
                              {(a.enrichment.departments ?? []).slice(0, 2).map((dp) => (
                                <Tag
                                  key={`dp-${dp}`}
                                  color="geekblue"
                                  style={{ margin: 0, fontSize: 10, padding: '0 4px', lineHeight: '15px', cursor: 'pointer' }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setDepartmentFilter((cur) => cur.includes(dp) ? cur : [...cur, dp]);
                                  }}
                                >
                                  {dp}
                                </Tag>
                              ))}
                            </div>
                          )}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3, fontSize: 11, color: '#94a3b8' }}>
                            <span>{a.source_name || '未知来源'}</span>
                            <span>·</span>
                            <span>{formatRelative(a.published_at)}</span>
                          </div>
                        </div>
                        <Button
                          type="text"
                          size="small"
                          icon={a.starred ? <StarFilled style={{ color: '#fbbf24' }} /> : <StarOutlined style={{ color: '#94a3b8' }} />}
                          onClick={(e) => handleStar(a, e)}
                        />
                      </div>
                    </div>
                  </List.Item>
                );
              }}
            />
            </div>
            <div style={{ flex: '0 0 auto', padding: '8px 12px', borderTop: '1px solid #e2e8f0', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              {/* 左下角：上页 / 下页 / 文章数量 — 方便对几万条文章逐页重建标签 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Tooltip title="上一页">
                  <Button
                    size="small"
                    icon={<LeftOutlined />}
                    disabled={currentPage <= 1 || loading}
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  >
                    上页
                  </Button>
                </Tooltip>
                <Tooltip title="下一页">
                  <Button
                    size="small"
                    icon={<RightOutlined />}
                    disabled={currentPage >= Math.max(1, Math.ceil(totalArticles / pageSize)) || loading}
                    onClick={() => setCurrentPage(currentPage + 1)}
                  >
                    下页
                  </Button>
                </Tooltip>
                <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                  第 <Text strong>{currentPage}</Text> / {Math.max(1, Math.ceil(totalArticles / pageSize))} 页
                  <span style={{ marginLeft: 8, color: '#94a3b8' }}>·</span>
                  <span style={{ marginLeft: 8 }}>共 <Text strong style={{ color: '#6366f1' }}>{totalArticles.toLocaleString()}</Text> 条</span>
                </Text>
              </div>
              <Pagination
                size="small"
                current={currentPage}
                pageSize={pageSize}
                total={totalArticles}
                showSizeChanger
                showQuickJumper
                showLessItems
                pageSizeOptions={['20', '50', '100', '200']}
                onChange={(page, size) => {
                  setCurrentPage(page);
                  setPageSize(size);
                }}
                onShowSizeChange={(_current, size) => {
                  setCurrentPage(1);
                  setPageSize(size);
                }}
              />
            </div>
            </>
          )}
        </div>

        {/* 拖拽分隔条：中-右 */}
        <div
          style={{ flex: '0 0 6px', cursor: 'col-resize', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onMouseDown={(e) => {
            e.preventDefault();
            dragRef.current = { side: 'right', startX: e.clientX, startLeft: leftWidth, startMid: midWidth };
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
          }}
        >
          <div style={{ width: 2, height: 32, background: '#cbd5e1', borderRadius: 1 }} />
        </div>

        {/* 右：正文 */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 20px',
            background: '#fcfcfd',
          }}
        >
          {detailLoading ? (
            <div style={{ padding: 80, textAlign: 'center' }}><Spin /></div>
          ) : !articleDetail ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={<span style={{ color: '#64748b', fontSize: 12 }}>选择左侧文章查看正文</span>}
              style={{ marginTop: 80 }}
            />
          ) : (
            <div>
              <Title level={4} style={{ marginTop: 0, lineHeight: 1.4 }}>
                {articleDetail.title}
              </Title>
              <div style={{ marginBottom: 14, fontSize: 12, color: '#64748b' }}>
                {articleDetail.source_name} · {formatRelative(articleDetail.published_at)}
                {articleDetail.url && (
                  <a
                    href={articleDetail.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ marginLeft: 10, color: '#6366f1' }}
                  >
                    <LinkOutlined /> 原文
                  </a>
                )}
              </div>
              {articleDetail.is_financial_event && (
                <Tag color="gold" icon={<ThunderboltOutlined />} style={{ marginBottom: 14 }}>
                  财务事件
                </Tag>
              )}
              {/* Enrichment 区块：股票 + 行业 + 事件 + 情感 + 国家 + 地区 + 关键词 + 日期 */}
              {articleDetail.enrichment && (
                articleDetail.enrichment.tickers.length > 0 ||
                articleDetail.enrichment.industries.length > 0 ||
                articleDetail.enrichment.event_tags.length > 0 ||
                (articleDetail.enrichment.countries?.length ?? 0) > 0 ||
                (articleDetail.enrichment.regions?.length ?? 0) > 0 ||
                (articleDetail.enrichment.key_terms?.length ?? 0) > 0 ||
                (articleDetail.enrichment.date_entities?.length ?? 0) > 0 ||
                (articleDetail.enrichment.provinces?.length ?? 0) > 0 ||
                (articleDetail.enrichment.cities?.length ?? 0) > 0 ||
                (articleDetail.enrichment.politicians?.length ?? 0) > 0 ||
                (articleDetail.enrichment.visits?.length ?? 0) > 0 ||
                (articleDetail.enrichment.departments?.length ?? 0) > 0 ||
                articleDetail.enrichment.sentiment_label
              ) && (
                <div
                  style={{
                    marginBottom: 16,
                    padding: 12,
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: 6,
                  }}
                >
                  {articleDetail.enrichment.sentiment_label && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>情感:</Text>
                      <Tag
                        color={
                          articleDetail.enrichment.sentiment_label === 'bullish' ? 'red'
                          : articleDetail.enrichment.sentiment_label === 'bearish' ? 'green'
                          : 'default'
                        }
                        style={{
                          margin: 0,
                          fontWeight: Math.abs(articleDetail.enrichment.sentiment_score ?? 0) >= 0.5 ? 700 : 500,
                        }}
                      >
                        {articleDetail.enrichment.sentiment_label === 'bullish' && <>
                          {(articleDetail.enrichment.sentiment_score ?? 0) >= 0.5 ? <FireOutlined /> : <RiseOutlined />} 利好
                        </>}
                        {articleDetail.enrichment.sentiment_label === 'bearish' && <>
                          {(articleDetail.enrichment.sentiment_score ?? 0) <= -0.5 ? <FireOutlined /> : <ArrowDownOutlined />} 利空
                        </>}
                        {articleDetail.enrichment.sentiment_label === 'neutral' && <><MinusOutlined /> 中性</>}
                        {articleDetail.enrichment.sentiment_score != null && ` ${articleDetail.enrichment.sentiment_score.toFixed(3)}`}
                        {articleDetail.enrichment.sentiment_confidence != null && ` · 置信度 ${(articleDetail.enrichment.sentiment_confidence * 100).toFixed(0)}%`}
                      </Tag>
                    </div>
                  )}
                  {articleDetail.enrichment.tickers.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>相关股票:</Text>
                      {articleDetail.enrichment.tickers.map((t) => (
                        <Tag key={`d-tk-${t}`} color="blue" style={{ marginBottom: 4 }}>{t}</Tag>
                      ))}
                    </div>
                  )}
                  {articleDetail.enrichment.industries.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>行业:</Text>
                      {articleDetail.enrichment.industries.map((ind) => (
                        <Tag key={`d-ind-${ind}`} color="geekblue" style={{ marginBottom: 4 }}>{ind}</Tag>
                      ))}
                    </div>
                  )}
                  {articleDetail.enrichment.event_tags.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>事件:</Text>
                      {articleDetail.enrichment.event_tags.map((ev) => (
                        <Tag key={`d-ev-${ev}`} color="orange" style={{ marginBottom: 4 }}>{ev}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.countries?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>国家:</Text>
                      {(articleDetail.enrichment.countries ?? []).map((co) => (
                        <Tag key={`d-co-${co}`} color="purple" style={{ marginBottom: 4 }}>{co}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.regions?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>地区:</Text>
                      {(articleDetail.enrichment.regions ?? []).map((rg) => (
                        <Tag key={`d-rg-${rg}`} color="cyan" style={{ marginBottom: 4 }}>{rg}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.key_terms?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>关键词:</Text>
                      {(articleDetail.enrichment.key_terms ?? []).map((kt) => (
                        <Tag key={`d-kt-${kt}`} color="magenta" style={{ marginBottom: 4 }}>{kt}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.date_entities?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>提及日期:</Text>
                      {(articleDetail.enrichment.date_entities ?? []).map((dt) => (
                        <Tag key={`d-dt-${dt}`} color="default" style={{ marginBottom: 4 }}>{dt}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.provinces?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>省份:</Text>
                      {(articleDetail.enrichment.provinces ?? []).map((pv) => (
                        <Tag key={`d-pv-${pv}`} color="volcano" style={{ marginBottom: 4 }}>{pv}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.cities?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>城市:</Text>
                      {(articleDetail.enrichment.cities ?? []).map((ct) => (
                        <Tag key={`d-ct-${ct}`} color="gold" style={{ marginBottom: 4 }}>{ct}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.politicians?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>领导人:</Text>
                      {(articleDetail.enrichment.politicians ?? []).map((pl) => (
                        <Tag key={`d-pl-${pl}`} color="red" style={{ marginBottom: 4 }}>{pl}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.visits?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>调研:</Text>
                      {(articleDetail.enrichment.visits ?? []).map((vs) => (
                        <Tag key={`d-vs-${vs}`} color="lime" style={{ marginBottom: 4 }}>{vs}</Tag>
                      ))}
                    </div>
                  )}
                  {(articleDetail.enrichment.departments?.length ?? 0) > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>部门:</Text>
                      {(articleDetail.enrichment.departments ?? []).map((dp) => (
                        <Tag key={`d-dp-${dp}`} color="geekblue" style={{ marginBottom: 4 }}>{dp}</Tag>
                      ))}
                    </div>
                  )}
                  {articleDetail.enrichment.entity_sentiments && Object.keys(articleDetail.enrichment.entity_sentiments).length > 0 && (
                    <div>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 8 }}>实体级情感:</Text>
                      {Object.entries(articleDetail.enrichment.entity_sentiments)
                        .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
                        .map(([key, score]) => {
                          const [kind, name] = key.split(':', 2);
                          const isPos = score > 0;
                          const strong = Math.abs(score) >= 0.5;
                          const label = ({
                            ticker: '股',
                            country: '国',
                            region: '区',
                            key_term: '词',
                            province: '省',
                            city: '市',
                            politician: '人',
                            department: '部',
                          } as any)[kind] ?? kind;
                          return (
                            <Tag
                              key={`es-${key}`}
                              color={isPos ? 'red' : 'green'}
                              style={{ marginBottom: 4, fontWeight: strong ? 700 : 400 }}
                            >
                              <span style={{ opacity: 0.6, marginRight: 4 }}>{label}</span>
                              {name} {score > 0 ? '+' : ''}{score.toFixed(2)}
                            </Tag>
                          );
                        })}
                    </div>
                  )}
                </div>
              )}
              {articleDetail.content_html ? (
                <div
                  className="news-content"
                  style={{ fontSize: 14, lineHeight: 1.75 }}
                  dangerouslySetInnerHTML={{ __html: articleDetail.content_html }}
                />
              ) : (
                <Paragraph style={{ fontSize: 14, lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
                  {articleDetail.content || articleDetail.summary || '(正文为空)'}
                </Paragraph>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NewsPanel;
