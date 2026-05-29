import { create } from 'zustand';
import { 
  getWorkingPoolFromBackend, 
  syncWorkingPoolToBackend, 
  listSavedPoolVersions,
  activatePoolVersion,
  saveWorkingPoolVersion,
  deleteSavedPoolVersion,
  type WorkingPoolItemV2, 
  type SavedPoolVersionV2 
} from '../services/wizardV2Service';
import type { Condition, QlibParams } from '../types';

interface WizardV2State {
  // Step 1 & 2
  workingPool: WorkingPoolItemV2[];
  savedPools: SavedPoolVersionV2[];
  activePoolVersionId?: string;
  selectedSymbols: string[];
  currentPoolName: string;
  conditions: Condition | null;

  // Step 3 & 4
  qlibParams: QlibParams;
  generated?: { code: string };
  validationResult: any | null;
  saveStatus: {
    savedToCloud: boolean;
    downloaded: boolean;
    lastSavedId?: string;
  };

  dirty: boolean;
  syncStatus: 'idle' | 'syncing' | 'synced' | 'degraded' | 'error';

  // Actions
  setWorkingPool: (items: WorkingPoolItemV2[], skipSync?: boolean) => void;
  addWorkingPoolItem: (item: WorkingPoolItemV2) => void;
  removeWorkingPoolItem: (symbol: string) => void;
  setSelectedSymbols: (symbols: string[]) => void;
  setCurrentPoolName: (name: string) => void;
  setConditions: (c: Condition | null) => void;
  setQlibParams: (p: QlibParams) => void;
  setGenerated: (g: { code: string } | undefined) => void;
  setValidationResult: (r: any | null) => void;
  markAsCloudSaved: (id: string) => void;
  markAsDownloaded: () => void;

  fetchWorkingPool: () => Promise<void>;
  fetchSavedPools: () => Promise<void>;
  saveCurrentPoolAsVersion: (name: string) => Promise<boolean>;
  activateVersion: (id: string) => Promise<boolean>;
  deleteSavedPool: (id: string) => Promise<boolean>;
  setSyncStatus: (status: WizardV2State['syncStatus']) => void;
  markClean: () => void;
}

export const useWizardV2Store = create<WizardV2State>((set, get) => ({
  workingPool: [],
  savedPools: [],
  activePoolVersionId: undefined,
  selectedSymbols: [],
  currentPoolName: '我的股票池',
  conditions: null,
  qlibParams: {
    strategy_type: 'TopkDropout',
    topk: 10,
    n_drop: 2,
    rebalance_days: 5,
    rebalance_period: 'weekly',
  },
  generated: undefined,
  validationResult: null,
  saveStatus: {
    savedToCloud: false,
    downloaded: false,
  },
  dirty: false,
  syncStatus: 'idle',

  setWorkingPool: (workingPool, skipSync) => {
    set({ 
      workingPool: [...workingPool], 
      selectedSymbols: workingPool.map(x => x.symbol),
      dirty: !skipSync 
    });
    if (!skipSync) {
      syncWorkingPoolToBackend(workingPool);
    }
  },

  addWorkingPoolItem: (item) => {
    const exists = get().workingPool.some(x => x.symbol === item.symbol);
    if (exists) return;
    const newPool = [...get().workingPool, item];
    set({ workingPool: newPool, dirty: true });
    syncWorkingPoolToBackend(newPool);
  },

  removeWorkingPoolItem: (symbol) => {
    const newPool = get().workingPool.filter((x) => x.symbol !== symbol);
    const newSelected = get().selectedSymbols.filter(x => x !== symbol);
    set({ workingPool: newPool, selectedSymbols: newSelected, dirty: true });
    syncWorkingPoolToBackend(newPool);
  },

  setCurrentPoolName: (currentPoolName) => set({ currentPoolName }),

  setSelectedSymbols: (selectedSymbols) => set({ selectedSymbols }),

  setConditions: (conditions) => set({ conditions }),
  setQlibParams: (qlibParams) => set({ qlibParams }),
  setGenerated: (generated) => set({ generated }),
  setValidationResult: (validationResult) => set({ validationResult }),
  markAsCloudSaved: (id) => set({ saveStatus: { ...get().saveStatus, savedToCloud: true, lastSavedId: id } }),
  markAsDownloaded: () => set({ saveStatus: { ...get().saveStatus, downloaded: true } }),

  fetchWorkingPool: async () => {
    set({ syncStatus: 'syncing' });
    try {
      const items = await getWorkingPoolFromBackend();
      set({ workingPool: items, dirty: false, syncStatus: 'synced' });
    } catch (err) {
      set({ syncStatus: 'error' });
    }
  },

  fetchSavedPools: async () => {
    try {
      const pools = await listSavedPoolVersions();
      set({ savedPools: pools });
    } catch (err) {
      console.error('Fetch saved pools failed', err);
    }
  },

  saveCurrentPoolAsVersion: async (name: string) => {
    const symbols = get().workingPool.map(x => x.symbol);
    const result = await saveWorkingPoolVersion(name, symbols);
    if (result) {
      await get().fetchSavedPools();
      set({ dirty: false });
      return true;
    }
    return false;
  },

  activateVersion: async (id: string) => {
    const success = await activatePoolVersion(id);
    if (success) {
      set({ activePoolVersionId: id });
    }
    return success;
  },
  
  deleteSavedPool: async (id: string) => {
    const success = await deleteSavedPoolVersion(id);
    if (success) {
      await get().fetchSavedPools();
    }
    return success;
  },

  setSyncStatus: (syncStatus) => set({ syncStatus }),
  markClean: () => set({ dirty: false }),
}));
