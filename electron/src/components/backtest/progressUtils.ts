export const getTimeBasedProgressTarget = (elapsedMs: number): number => {
  if (elapsedMs < 5_000) return 12;
  if (elapsedMs < 15_000) return 24;
  if (elapsedMs < 30_000) return 38;
  if (elapsedMs < 60_000) return 52;
  if (elapsedMs < 120_000) return 66;
  if (elapsedMs < 240_000) return 78;
  if (elapsedMs < 480_000) return 86;
  return 92;
};

export const getBacktestStageMessage = (
  displayProgress: number,
  backendProgress: number,
  status?: string,
  backendMessage?: string
): string => {
  if (status === 'retrying') return '正在重试连接后端...';
  if (status === 'completed') return '正在加载回测结果...';
  if (backendMessage) return backendMessage;
  if (backendProgress >= 98 || displayProgress >= 98) return '正在写入结果并生成报告...';
  if (backendProgress >= 85 || displayProgress >= 85) return '正在汇总绩效指标...';
  if (backendProgress >= 60 || displayProgress >= 60) return '正在执行回测撮合与净值计算...';
  if (backendProgress >= 30 || displayProgress >= 30) return '正在加载信号与交易日历...';
  return '正在准备回测任务...';
};

export const blendBacktestProgress = (
  currentProgress: number,
  backendProgress: number,
  elapsedMs: number
): number => {
  const timeTarget = getTimeBasedProgressTarget(elapsedMs);
  const backendAnchoredCap = backendProgress > 0 ? Math.min(backendProgress + 6, 97) : 92;
  const target = Math.max(currentProgress, Math.min(timeTarget, backendAnchoredCap));
  const next = currentProgress + Math.max(0.2, (target - currentProgress) * 0.18);
  return Math.min(target, next);
};
