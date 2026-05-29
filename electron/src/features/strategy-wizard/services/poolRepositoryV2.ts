import {
  fetchWorkingPoolByDsl,
  listSavedPoolVersions,
  loadSavedPoolSymbols,
  saveWorkingPoolVersion,
  type SavedPoolVersionV2,
  type WorkingPoolItemV2,
} from './wizardV2Service';

export interface SavePoolVersionRequestV2 {
  name: string;
  symbols: string[];
}

export interface SavePoolVersionResponseV2 {
  id: string;
  name: string;
  stockCount: number;
  createdAt: string;
}

/**
 * V2 仓储层占位：
 * 后续在此收敛 Working/Saved/Active 的接口调用，避免 UI 直接拼接请求。
 */
export class PoolRepositoryV2 {
  async queryWorkingPoolByDsl(dsl: string): Promise<WorkingPoolItemV2[]> {
    return fetchWorkingPoolByDsl(dsl);
  }

  async savePoolVersion(req: SavePoolVersionRequestV2): Promise<SavePoolVersionResponseV2> {
    const result = await saveWorkingPoolVersion(req.name, req.symbols);
    if (!result) {
      throw new Error('保存股票池版本失败');
    }
    return result;
  }

  async listSavedPoolVersions(): Promise<SavedPoolVersionV2[]> {
    return listSavedPoolVersions();
  }

  async loadSavedPoolSymbols(fileKey: string): Promise<string[]> {
    return loadSavedPoolSymbols(fileKey);
  }
}

export const poolRepositoryV2 = new PoolRepositoryV2();
