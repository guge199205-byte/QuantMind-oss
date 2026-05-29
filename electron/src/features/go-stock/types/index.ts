// go-stock API types

export interface Telegraph {
  ID?: number;
  title: string;
  content: string;
  time: string;
  dataTime?: string;
  url: string;
  source: string;
  isRed: boolean;
  sentimentResult?: string;
}

export interface GlobalStockIndex {
  ID?: number;
  name: string;
  code: string;
  price: string;
  changePercent: string;
  changeAmount: string;
  region?: string;
  updateTime?: string;
}

export interface KLineData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  amount: number;
  amplitude?: number;
  changePercent?: number;
  changeAmount?: number;
  turnoverRate?: number;
}

export interface IndustryRank {
  name?: string;
  code?: string;
  changepercent?: string;
  leading?: string;
  leading_price?: string;
  leading_change?: string;
  [key: string]: any;
}

export interface HotItem {
  ID?: number;
  name: string;
  code?: string;
  value?: string;
  url?: string;
  createdAt?: string;
}

export interface HotEvent {
  ID?: number;
  title: string;
  content?: string;
  url?: string;
  createdAt?: string;
}

export interface StockBasic {
  ID?: number;
  tsCode?: string;
  symbol?: string;
  name?: string;
  area?: string;
  industry?: string;
  market?: string;
  listDate?: string;
  [key: string]: any;
}

export interface StockRealtime {
  code: string;
  name: string;
  price: string;
  changePercent: number;
  changePrice: number;
  open: string;
  high: string;
  low: string;
  preClose: string;
  volume: string;
  amount: string;
  market: string;
  [key: string]: any;
}

export interface LongTigerRankData {
  ID?: number;
  stockCode?: string;
  stockName?: string;
  closePrice?: string;
  changePercent?: string;
  buyAmount?: string;
  sellAmount?: string;
  netAmount?: string;
  reason?: string;
  date?: string;
  [key: string]: any;
}

export interface FundBasic {
  ID?: number;
  code?: string;
  name?: string;
  type?: string;
  netValue?: string;
  totalNetValue?: string;
  dayGrowth?: string;
  [key: string]: any;
}

export interface FollowedFund {
  ID?: number;
  code?: string;
  name?: string;
  netValue?: string;
  totalNetValue?: string;
  dayGrowth?: string;
  estimatedValue?: string;
  estimatedGrowth?: string;
  [key: string]: any;
}

export interface StockChangesResponse {
  total: number;
  data: any[];
}
