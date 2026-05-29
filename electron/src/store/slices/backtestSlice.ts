import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface BacktestState {
  results: any[];
  currentResult: any | null;
  loading: boolean;
  error: string | null;
}

const initialState: BacktestState = {
  results: [],
  currentResult: null,
  loading: false,
  error: null,
};

const backtestSlice = createSlice({
  name: 'backtest',
  initialState,
  reducers: {
    setResults: (state, action: PayloadAction<any[]>) => {
      state.results = action.payload;
    },
    setCurrentResult: (state, action: PayloadAction<any>) => {
      state.currentResult = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setResults, setCurrentResult, setLoading, setError } = backtestSlice.actions;
export default backtestSlice.reducer;
