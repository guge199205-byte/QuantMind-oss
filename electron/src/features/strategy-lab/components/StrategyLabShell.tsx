/**
 * StrategyLabShell — page chrome that matches the look of NewBacktestCenterPage:
 *   - Rounded white card frame (32px radius) on a slate page background
 *   - Top header with gradient Q logo + "QuantMind / 策略实验室" title
 *   - Breadcrumb row
 *   - framer-motion AnimatePresence for inner content swap
 *
 * The actual editor + run controls + result panel live in StrategyLabPage as
 * children so this file only owns presentation.
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bell } from 'lucide-react';
import { PAGE_LAYOUT } from '../../../config/pageLayout';

interface Props {
  /** Optional inline breadcrumb tail (current sub-tab/mode). When omitted, only "策略实验室" is shown — but the consumer typically renders its own inline breadcrumb so this can stay undefined. */
  activeLabel?: string;
  /** Optional right-side toolbar slot. */
  rightActions?: React.ReactNode;
  children: React.ReactNode;
  /** Stable key for AnimatePresence — change to retrigger fade. */
  contentKey?: string;
  /** When true, skip rendering the standalone breadcrumb row entirely. */
  hideBreadcrumb?: boolean;
}

export const StrategyLabShell: React.FC<Props> = ({
  activeLabel,
  rightActions,
  children,
  contentKey,
  hideBreadcrumb = false,
}) => {
  const breadcrumb = ['策略实验室', activeLabel || ''].filter(Boolean);

  return (
    <div className={PAGE_LAYOUT.outerClass}>
      <div className={PAGE_LAYOUT.frameClass}>
        <header
          className={PAGE_LAYOUT.headerClass}
          style={{ height: `${PAGE_LAYOUT.headerHeight}px` }}
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-2xl flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-lg">Q</span>
              </div>
              <div className="flex items-center gap-2.5 ml-1">
                <h1 className="text-xl font-bold text-slate-800 tracking-tight">QuantMind</h1>
                <div className="h-4 w-[1px] bg-slate-200 self-center" />
                <span className="text-sm font-medium text-slate-500">策略实验室</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {rightActions}
            <button className="p-2 hover:bg-gray-100 rounded-2xl transition-colors">
              <Bell className="w-5 h-5 text-gray-600" />
            </button>
          </div>
        </header>

        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 flex flex-col bg-gray-50/50 min-w-0">
            {!hideBreadcrumb && breadcrumb.length > 0 && (
              <div className={PAGE_LAYOUT.breadcrumbClass}>
                <div className="flex items-center gap-2 text-sm">
                  {breadcrumb.map((item, idx) => (
                    <React.Fragment key={idx}>
                      {idx > 0 && <span className="text-gray-400">/</span>}
                      <span
                        className={
                          idx === breadcrumb.length - 1
                            ? 'text-gray-800 font-medium'
                            : 'text-gray-500'
                        }
                      >
                        {item}
                      </span>
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}

            <div
              className="flex-1 overflow-auto custom-scrollbar overflow-x-hidden"
              style={{
                scrollbarWidth: 'thin',
                scrollbarColor: '#cbd5e1 #f1f5f9',
              }}
            >
              <div className="px-6 py-4 h-full">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={contentKey || 'lab-default'}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.2 }}
                    className="h-full"
                  >
                    {children}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default StrategyLabShell;
