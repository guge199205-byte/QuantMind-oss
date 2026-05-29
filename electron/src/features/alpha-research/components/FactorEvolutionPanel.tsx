import { useState, useEffect, useCallback } from 'react';
import { alphaAgentService, EvolutionTask } from '../services/alphaAgentService';

export function FactorEvolutionPanel({ userId }: { userId: string }) {
  const [direction, setDirection] = useState('');
  const [loopN, setLoopN] = useState(3);
  const [tasks, setTasks] = useState<EvolutionTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);

  const refreshTasks = useCallback(async () => {
    try {
      const list = await alphaAgentService.listTasks(userId);
      setTasks(list);
    } catch {
      // ignore
    }
  }, [userId]);

  useEffect(() => {
    refreshTasks();
    const iv = setInterval(refreshTasks, 10000);
    return () => clearInterval(iv);
  }, [refreshTasks]);

  const handleStart = async () => {
    if (!direction.trim()) return;
    setStarting(true);
    try {
      await alphaAgentService.startEvolution({
        user_id: userId,
        loop_n: loopN,
        direction: direction.trim(),
      });
      setDirection('');
      await refreshTasks();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(msg);
    } finally {
      setStarting(false);
    }
  };

  const handleCancel = async (taskId: string) => {
    try {
      await alphaAgentService.cancelTask(taskId);
      await refreshTasks();
    } catch {
      // ignore
    }
  };

  const statusColor: Record<string, string> = {
    pending: '#888',
    running: '#4CAF50',
    completed: '#2196F3',
    failed: '#f44336',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16 }}>
      <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>因子演化</h3>

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12, color: '#aaa', marginBottom: 4, display: 'block' }}>
            挖掘方向 / 假设
          </label>
          <input
            type="text"
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            placeholder="例如：挖掘基于波动率的动量因子..."
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: 6,
              border: '1px solid #333',
              background: '#1a1a2e',
              color: '#eee',
              fontSize: 13,
            }}
            onKeyDown={(e) => e.key === 'Enter' && handleStart()}
          />
        </div>
        <div>
          <label style={{ fontSize: 12, color: '#aaa', marginBottom: 4, display: 'block' }}>
            轮数
          </label>
          <input
            type="number"
            min={1}
            max={20}
            value={loopN}
            onChange={(e) => setLoopN(Number(e.target.value))}
            style={{
              width: 60,
              padding: '8px',
              borderRadius: 6,
              border: '1px solid #333',
              background: '#1a1a2e',
              color: '#eee',
              fontSize: 13,
              textAlign: 'center',
            }}
          />
        </div>
        <button
          onClick={handleStart}
          disabled={starting || !direction.trim()}
          style={{
            padding: '8px 20px',
            borderRadius: 6,
            border: 'none',
            background: starting || !direction.trim() ? '#555' : '#4CAF50',
            color: '#fff',
            fontWeight: 600,
            cursor: starting || !direction.trim() ? 'not-allowed' : 'pointer',
            fontSize: 13,
          }}
        >
          {starting ? '启动中...' : '启动演化'}
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {tasks.length === 0 && (
          <div style={{ color: '#666', fontSize: 13, textAlign: 'center', padding: 20 }}>
            暂无演化任务，输入方向后点击「启动演化」
          </div>
        )}
        {tasks.map((t) => (
          <div
            key={t.task_id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 12px',
              borderRadius: 6,
              background: '#1a1a2e',
              border: '1px solid #222',
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: statusColor[t.status] || '#888',
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: 12, color: '#888', fontFamily: 'monospace', width: 100 }}>
              {t.task_id.slice(0, 12)}
            </span>
            <span style={{ flex: 1, fontSize: 13, color: '#ccc' }}>{t.progress || t.status}</span>
            {t.status === 'running' && (
              <button
                onClick={() => handleCancel(t.task_id)}
                style={{
                  padding: '2px 8px',
                  borderRadius: 4,
                  border: '1px solid #f44336',
                  background: 'transparent',
                  color: '#f44336',
                  fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
            )}
            {t.error_message && (
              <span style={{ fontSize: 11, color: '#f44336', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {t.error_message.slice(0, 60)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
