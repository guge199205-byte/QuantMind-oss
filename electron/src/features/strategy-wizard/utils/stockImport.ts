import Papa from 'papaparse';
import { StockItem } from '../types';

export interface StockIndexItem {
  symbol: string;
  code: string;
  name: string;
}

/**
 * Extracts 6-digit stock code from a string.
 * Example: 'sz000001' -> '000001', '600036.SH' -> '600036'
 */
export const extract6DigitCode = (text: string): string | null => {
  const match = text.match(/\d{6}/);
  return match ? match[0] : null;
};

const HEADER_CANDIDATES = [
  '代码',
  '股票代码',
  '证券代码',
  'symbol',
  'ticker',
  'ts_code',
  'wind_code',
  'stock_code',
  'code',
];

const normalizeHeader = (header: string): string => String(header || '').trim().toLowerCase();

const detectCodeColumn = (headers: string[]): number => {
  const normalized = headers.map(normalizeHeader);
  for (const candidate of HEADER_CANDIDATES) {
    const idx = normalized.indexOf(candidate.toLowerCase());
    if (idx >= 0) return idx;
  }
  return -1;
};

const parseRowCode = (value: unknown): string | null => {
  const raw = String(value ?? '').trim().toUpperCase();
  if (!raw) return null;
  const digit = extract6DigitCode(raw);
  return digit || null;
};

/**
 * Parses CSV and matches 6-digit codes against a provided index.
 * @param file The CSV file
 * @param indexItems The list of all stocks from stocks_index.json
 * @param columnIdx The column index (0-based, so 5 for 6th column)
 */
export const parseAndMatchStocks = async (
  file: File,
  indexItems: StockIndexItem[],
  columnIdx: number = 5
): Promise<StockItem[]> => {
  return new Promise((resolve, reject) => {
    // 双索引匹配：6位code + 前缀symbol
    const codeMap = new Map<string, StockIndexItem>();
    const symbolMap = new Map<string, StockIndexItem>();
    indexItems.forEach(item => {
      codeMap.set(String(item.code || '').trim(), item);
      symbolMap.set(String(item.symbol || '').trim().toUpperCase(), item);
    });

    Papa.parse(file, {
      skipEmptyLines: true,
      complete: (results) => {
        const stocks: StockItem[] = [];
        const seen = new Set<string>();
        const rows = Array.isArray(results.data) ? results.data : [];
        if (!rows.length) {
          resolve([]);
          return;
        }

        // 优先识别表头中的代码列，否则退回调用方指定列
        const firstRow = Array.isArray(rows[0]) ? (rows[0] as any[]) : [];
        const detectedColumn = detectCodeColumn(firstRow.map((x) => String(x ?? '')));
        const targetColumn = detectedColumn >= 0 ? detectedColumn : columnIdx;
        const startRow = detectedColumn >= 0 ? 1 : 0;

        for (let i = startRow; i < rows.length; i += 1) {
          const row = rows[i];
          if (!Array.isArray(row) || row.length <= targetColumn) continue;

          const rawValue = row[targetColumn];
          const sixCode = parseRowCode(rawValue);
          if (!sixCode) continue;

          const matched = codeMap.get(sixCode) || symbolMap.get(String(rawValue || '').trim().toUpperCase());
          if (!matched || seen.has(matched.symbol)) continue;

          stocks.push({
            symbol: matched.symbol,
            name: matched.name,
          });
          seen.add(matched.symbol);
        }
        resolve(stocks);
      },
      error: (err) => reject(err),
    });
  });
};
