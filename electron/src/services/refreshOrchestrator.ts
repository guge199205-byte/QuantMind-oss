export type RefreshReason =
  | 'bootstrap'
  | 'manual'
  | 'visibility-visible'
  | 'dashboard-enter'
  | 'fallback-poll'
  | 'module-action'
  | 'external';

export interface RefreshContext {
  reason: RefreshReason;
  silent: boolean;
}

export type RefreshTask = (context: RefreshContext) => Promise<void> | void;

interface RefreshEntry {
  task: RefreshTask;
  minIntervalMs: number;
  lastRunAt: number;
  inflight: Promise<void> | null;
}

class RefreshOrchestrator {
  private readonly entries = new Map<string, RefreshEntry>();

  register(moduleId: string, task: RefreshTask, options?: { minIntervalMs?: number }): () => void {
    const entry: RefreshEntry = {
      task,
      minIntervalMs: options?.minIntervalMs ?? 800,
      lastRunAt: 0,
      inflight: null,
    };

    this.entries.set(moduleId, entry);

    return () => {
      const current = this.entries.get(moduleId);
      if (current === entry) {
        this.entries.delete(moduleId);
      }
    };
  }

  async requestRefresh(moduleId: string, reason: RefreshReason, silent = true): Promise<void> {
    const entry = this.entries.get(moduleId);
    if (!entry) {
      return;
    }

    if (entry.inflight) {
      await entry.inflight;
      return;
    }

    const now = Date.now();
    if (now - entry.lastRunAt < entry.minIntervalMs) {
      return;
    }

    const job = (async () => {
      await entry.task({ reason, silent });
      entry.lastRunAt = Date.now();
    })();

    entry.inflight = job;

    try {
      await job;
    } finally {
      entry.inflight = null;
    }
  }

  async requestAll(reason: RefreshReason, silent = true): Promise<void> {
    const moduleIds = Array.from(this.entries.keys());
    await Promise.all(moduleIds.map((moduleId) => this.requestRefresh(moduleId, reason, silent)));
  }
}

export const refreshOrchestrator = new RefreshOrchestrator();
