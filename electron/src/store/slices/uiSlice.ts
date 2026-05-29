import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface UIState {
  theme: 'light' | 'dark';
  sidebarOpen: boolean;
  notifications: any[];
  tradingMode: 'real' | 'simulation';
}

const TRADING_MODE_PREF_KEY = 'qm:trading_mode_pref';
const savedMode = localStorage.getItem(TRADING_MODE_PREF_KEY);
const initialTradingMode: 'real' | 'simulation' = 
  (savedMode === 'real' || savedMode === 'simulation') ? savedMode : 'simulation';

const initialState: UIState = {
  theme: 'light',
  sidebarOpen: true,
  notifications: [],
  tradingMode: initialTradingMode,
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setTheme: (state, action: PayloadAction<'light' | 'dark'>) => {
      state.theme = action.payload;
    },
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    addNotification: (state, action: PayloadAction<any>) => {
      state.notifications.push(action.payload);
    },
    removeNotification: (state, action: PayloadAction<string>) => {
      state.notifications = state.notifications.filter(n => n.id !== action.payload);
    },
    setTradingMode: (state, action: PayloadAction<'real' | 'simulation'>) => {
      state.tradingMode = action.payload;
    },
  },
});

export const { setTheme, toggleSidebar, addNotification, removeNotification, setTradingMode } = uiSlice.actions;
export default uiSlice.reducer;
