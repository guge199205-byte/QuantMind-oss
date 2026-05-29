/**
 * IndexedDB存储服务基类
 */

import { DatabaseConfig, StoreConfig, QueryOptions } from './types';

export class StorageService {
  protected db: IDBDatabase | null = null;
  protected dbName: string;
  protected version: number;
  protected stores: StoreConfig[];

  constructor(config: DatabaseConfig) {
    this.dbName = config.name;
    this.version = config.version;
    this.stores = config.stores;
  }

  /**
   * 初始化数据库
   */
  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);

      request.onerror = () => {
        reject(new Error(`无法打开数据库: ${request.error?.message}`));
      };

      request.onsuccess = () => {
        this.db = request.result;
        console.log(`数据库 ${this.dbName} 已打开`);
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        this.createStores(db);
      };
    });
  }

  /**
   * 创建对象存储
   */
  private createStores(db: IDBDatabase): void {
    for (const storeConfig of this.stores) {
      // 如果存储已存在，跳过
      if (db.objectStoreNames.contains(storeConfig.name)) {
        continue;
      }

      // 创建对象存储
      const store = db.createObjectStore(storeConfig.name, {
        keyPath: storeConfig.keyPath,
        autoIncrement: storeConfig.autoIncrement ?? true,
      });

      // 创建索引
      if (storeConfig.indexes) {
        for (const index of storeConfig.indexes) {
          store.createIndex(index.name, index.keyPath, {
            unique: index.unique ?? false,
            multiEntry: index.multiEntry ?? false,
          });
        }
      }

      console.log(`已创建对象存储: ${storeConfig.name}`);
    }
  }

  /**
   * 添加记录
   */
  async add<T>(storeName: string, data: T): Promise<IDBValidKey> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.add(data);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 批量添加记录
   */
  async addBatch<T>(storeName: string, dataArray: T[]): Promise<number> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      let successCount = 0;

      transaction.oncomplete = () => resolve(successCount);
      transaction.onerror = () => reject(transaction.error);

      for (const data of dataArray) {
        const request = store.add(data);
        request.onsuccess = () => successCount++;
      }
    });
  }

  /**
   * 获取记录
   */
  async get<T>(storeName: string, key: IDBValidKey): Promise<T | undefined> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.get(key);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 获取所有记录
   */
  async getAll<T>(storeName: string, options?: QueryOptions): Promise<T[]> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.getAll();

      request.onsuccess = () => {
        let results = request.result;

        // 应用查询选项
        if (options) {
          if (options.offset) {
            results = results.slice(options.offset);
          }
          if (options.limit) {
            results = results.slice(0, options.limit);
          }
        }

        resolve(results);
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 通过索引查询
   */
  async getByIndex<T>(
    storeName: string,
    indexName: string,
    value: IDBValidKey,
    options?: QueryOptions
  ): Promise<T[]> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readonly');
      const store = transaction.objectStore(storeName);
      const index = store.index(indexName);
      const request = index.getAll(value, options?.limit);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 更新记录
   */
  async update<T>(storeName: string, data: T): Promise<IDBValidKey> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.put(data);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 删除记录
   */
  async delete(storeName: string, key: IDBValidKey): Promise<void> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.delete(key);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 清空存储
   */
  async clear(storeName: string): Promise<void> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.clear();

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 获取记录数
   */
  async count(storeName: string): Promise<number> {
    this.ensureDb();
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(storeName, 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.count();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 确保数据库已初始化
   */
  protected ensureDb(): void {
    if (!this.db) {
      throw new Error('数据库未初始化，请先调用 init()');
    }
  }

  /**
   * 关闭数据库
   */
  close(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
      console.log(`数据库 ${this.dbName} 已关闭`);
    }
  }
}
