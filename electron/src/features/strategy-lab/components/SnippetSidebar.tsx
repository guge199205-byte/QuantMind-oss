/**
 * SnippetSidebar — example-strategy navigator styled to match BacktestSidebar.
 *
 * Visually identical to /backtest's left-rail "功能模块" pattern:
 *   - Section heading uppercase
 *   - Per-category icon chip (rounded square)
 *   - Title + description
 *   - Active blue indicator bar + spring layout animation
 *   - whileHover x:4 / whileTap scale:0.98 micro-interaction
 *
 * The strategy lab has 7 categories instead of a flat module list, so we
 * render each category as a collapsible section. Inside the section the
 * individual snippets reuse the same ModuleButton skeleton.
 */

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BookOpen,
  TrendingUp,
  RotateCcw,
  CalendarRange,
  BarChart2,
  LayoutGrid,
  Layers,
  Search,
  ChevronDown,
} from 'lucide-react';
import {
  STRATEGY_LAB_SNIPPETS,
  SNIPPETS_BY_CATEGORY,
  CATEGORY_LABELS,
  type SnippetCategory,
  type SnippetSpec,
} from './snippets';

const CATEGORY_ICON: Record<SnippetCategory, React.ComponentType<{ className?: string }>> = {
  basic: BookOpen,
  trend: TrendingUp,
  reversal: RotateCcw,
  timing: CalendarRange,
  volume: BarChart2,
  cross: LayoutGrid,
  factor: Layers,
};

const CATEGORY_COLOR: Record<SnippetCategory, { ring: string; chip: string; text: string }> = {
  basic:    { ring: 'bg-blue-500/10',    chip: 'bg-blue-100',    text: 'text-blue-600' },
  trend:    { ring: 'bg-indigo-500/10',  chip: 'bg-indigo-100',  text: 'text-indigo-600' },
  reversal: { ring: 'bg-purple-500/10',  chip: 'bg-purple-100',  text: 'text-purple-600' },
  timing:   { ring: 'bg-cyan-500/10',    chip: 'bg-cyan-100',    text: 'text-cyan-600' },
  volume:   { ring: 'bg-orange-500/10',  chip: 'bg-orange-100',  text: 'text-orange-600' },
  cross:    { ring: 'bg-green-500/10',   chip: 'bg-green-100',   text: 'text-green-600' },
  factor:   { ring: 'bg-pink-500/10',    chip: 'bg-pink-100',    text: 'text-pink-600' },
};

const CATEGORY_DESC: Record<SnippetCategory, string> = {
  basic: '入门起点，单标的快速验证',
  trend: '均线 / 突破 / 通道趋势跟随',
  reversal: '均值回归 / 超卖反弹',
  timing: '日历事件 / 月初效应等择时',
  volume: '成交量与价格联合确认',
  cross: '横截面排名与轮动',
  factor: '多因子复合信号',
};

interface Props {
  activeSnippetId: string;
  onSelect: (id: string) => void;
}

export const SnippetSidebar: React.FC<Props> = ({ activeSnippetId, onSelect }) => {
  const [query, setQuery] = React.useState('');
  const [openCats, setOpenCats] = React.useState<Set<SnippetCategory>>(
    () => new Set(['basic', 'trend']),
  );

  const matches = (s: SnippetSpec) => {
    const q = query.trim().toLowerCase();
    return (
      !q ||
      s.title.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.id.toLowerCase().includes(q)
    );
  };

  const filteredByCat = useMemo(() => {
    const cats: SnippetCategory[] = ['basic', 'trend', 'reversal', 'timing', 'volume', 'cross', 'factor'];
    return cats.map((cat) => ({
      cat,
      list: SNIPPETS_BY_CATEGORY[cat].filter(matches),
    }));
  }, [query]);

  const toggleCat = (cat: SnippetCategory) => {
    setOpenCats((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  // When user is searching, expand every category that has matches
  const isSearching = query.trim().length > 0;

  return (
    <aside className="bg-white border border-gray-200 rounded-2xl shadow-sm flex flex-col h-full overflow-hidden">
      <div className="px-5 pt-4 pb-3 border-b border-gray-100">
        <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
          策略库
        </p>
        <h2 className="text-lg font-bold text-slate-800 tracking-tight">示例策略</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          {STRATEGY_LAB_SNIPPETS.length} 个可运行示例 · 7 大类别
        </p>
        <div className="relative mt-3">
          <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索示例…"
            className="w-full pl-8 pr-2 py-1.5 text-xs border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-300 transition"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar py-3">
        {filteredByCat.every(({ list }) => list.length === 0) && (
          <div className="px-5 py-6 text-center text-xs text-gray-500">没有匹配的示例</div>
        )}

        {filteredByCat.map(({ cat, list }) => {
          if (list.length === 0) return null;
          const Icon = CATEGORY_ICON[cat];
          const colors = CATEGORY_COLOR[cat];
          const isOpen = isSearching || openCats.has(cat);

          return (
            <div key={cat} className="mb-2">
              <motion.button
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.985 }}
                onClick={() => !isSearching && toggleCat(cat)}
                className="w-full px-5 py-2 flex items-center gap-3 hover:bg-gray-50 transition-colors text-left"
              >
                <div className={`w-9 h-9 rounded-2xl flex items-center justify-center shadow-sm ${colors.ring}`}>
                  <Icon className={`w-[18px] h-[18px] ${colors.text}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-[15px] text-slate-800 tracking-tight">
                      {CATEGORY_LABELS[cat]}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${colors.chip} ${colors.text} font-medium`}>
                      {list.length}
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-500 truncate">{CATEGORY_DESC[cat]}</div>
                </div>
                <motion.div animate={{ rotate: isOpen ? 0 : -90 }} transition={{ duration: 0.2 }}>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </motion.div>
              </motion.button>

              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-0.5 mt-1">
                      {list.map((s) => (
                        <SnippetButton
                          key={s.id}
                          item={s}
                          isActive={activeSnippetId === s.id}
                          onClick={() => onSelect(s.id)}
                          accent={colors}
                        />
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>

      <div className="border-t border-gray-100 px-5 py-3 text-[11px] text-gray-500 leading-relaxed">
        SDK：<code className="text-slate-700">ctx.universe / start / end / cash</code>
        <br />
        钩子：<code className="text-slate-700">setup / on_bar / on_universe</code>
      </div>
    </aside>
  );
};

interface SnippetButtonProps {
  item: SnippetSpec;
  isActive: boolean;
  onClick: () => void;
  accent: { ring: string; chip: string; text: string };
}

const SnippetButton: React.FC<SnippetButtonProps> = ({ item, isActive, onClick, accent }) => {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ x: 4 }}
      whileTap={{ scale: 0.98 }}
      className={`relative w-full text-left transition-colors ${
        isActive ? 'bg-blue-50' : 'hover:bg-gray-50'
      }`}
    >
      {isActive && (
        <motion.div
          layoutId="snippet-active-bar"
          className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 rounded-r-full"
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        />
      )}
      <div className="flex items-start gap-2.5 pl-7 pr-4 py-2">
        <div
          className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${
            isActive ? 'bg-blue-500' : accent.text.replace('text-', 'bg-')
          } opacity-80`}
        />
        <div className="flex-1 min-w-0">
          <div
            className={`text-[13px] font-medium tracking-tight ${
              isActive ? 'text-blue-700' : 'text-slate-700'
            }`}
          >
            {item.title}
          </div>
          <div className="text-[11px] text-gray-500 leading-snug line-clamp-2">
            {item.description}
          </div>
        </div>
      </div>
    </motion.button>
  );
};

export default SnippetSidebar;
