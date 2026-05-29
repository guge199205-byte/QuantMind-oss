import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface MarketDataState {
  stocks: any[];
  selectedStock: any | null;
  loading: boolean;
  error: string | null;
}

const initialState: MarketDataState = {
  stocks: [],
  selectedStock: null,
  loading: false,
  error: null,
};

const marketDataSlice = createSlice({
  name: 'marketData',
  initialState,
  reducers: {
    setStocks: (state, action: PayloadAction<any[]>) => {
      state.stocks = action.payload;
    },
    setSelectedStock: (state, action: PayloadAction<any>) => {
      state.selectedStock = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setStocks, setSelectedStock, setLoading, setError } = marketDataSlice.actions;
export default marketDataSlice.reducer;
