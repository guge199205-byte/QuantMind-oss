import { researchService, type ResearchStockRow } from '../../../services/researchService';

const DEFAULT_BATCH_SIZE = 200;

/**
 * 将 symbol 列表按批次拉取投研特征，避免一次性请求过大时出现超时或前端硬截断。
 */
export async function loadFeaturesBySymbolsInBatches(
  symbols: string[],
  batchSize = DEFAULT_BATCH_SIZE,
  options?: { lite?: boolean }
): Promise<ResearchStockRow[]> {
  const list = (symbols || []).map((s) => String(s || '').trim()).filter(Boolean);
  if (!list.length) return [];

  const merged: ResearchStockRow[] = [];
  for (let i = 0; i < list.length; i += batchSize) {
    const batch = list.slice(i, i + batchSize);
    const items = await researchService.getFeaturesBySymbols(batch);
    merged.push(...items);
  }
  return merged;
}
