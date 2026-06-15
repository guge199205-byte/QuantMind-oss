/**
 * Strategy Lab AI assistant drawer.
 *
 * Day 8/9: passthrough to /api/v1/ai-ide/ai/chat (SSE), with:
 *   - "Insert into editor" button on the latest assistant turn
 *   - "Diff accept" path: extracts ```python fenced block and offers to
 *     replace the editor content
 *   - error humanization via humanizeError()
 *
 * Streaming uses fetch() ReadableStream because EventSource cannot send
 * Authorization headers, and the backend serves text/event-stream.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Drawer,
  Input,
  Button,
  Space,
  Typography,
  Tag,
  Empty,
  Tooltip,
  Modal,
  message,
} from 'antd';
import { SendOutlined, RobotOutlined, CodeOutlined } from '@ant-design/icons';
import { authService } from '../../auth/services/authService';
import { SERVICE_URLS } from '../../../config/services';
import { humanizeError } from '../utils/humanizeError';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
  /** Server-streaming flag. */
  streaming?: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** Current editor code — sent as context with each turn. */
  code: string;
  /** Last error from the runner — humanizeError-pre-massaged. */
  lastError?: { message?: string; traceback?: string } | null;
  /** Called when the user clicks "应用此代码" on a fenced ```python block. */
  onApplyCode: (newCode: string) => void;
}

const FENCE_RE = /```python\s*([\s\S]*?)```/i;

function extractFencedPython(content: string): string | null {
  const m = content.match(FENCE_RE);
  return m ? m[1].trim() : null;
}

const SUGGESTED_PROMPTS = [
  '在现有代码上加一条 RSI 指标做超卖反弹',
  '把买入条件改成 5 日均线上穿 20 日均线',
  '加一个 8% 止损 + 15% 止盈',
  '把 universe 换成 csi500',
  '修复上一次回测报的错误',
];

const StrategyLabAiDrawer: React.FC<Props> = ({ open, onClose, code, lastError, onApplyCode }) => {
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const cancelRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  useEffect(() => () => cancelRef.current?.abort(), []);

  const send = useCallback(async (rawMsg: string) => {
    const msg = rawMsg.trim();
    if (!msg || busy) return;

    const user: ChatTurn = { role: 'user', content: msg };
    const assistant: ChatTurn = { role: 'assistant', content: '', streaming: true };
    setHistory((h: ChatTurn[]) => [...h, user, assistant]);
    setInput('');
    setBusy(true);

    const baseUrl = String(SERVICE_URLS.ENGINE_SERVICE || '').replace(/\/+$/, '');
    const url = `${baseUrl}/api/v1/ai-ide/ai/chat`;
    const token = authService.getAccessToken();

    const controller = new AbortController();
    cancelRef.current = controller;

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
        body: JSON.stringify({
          message: msg,
          current_code: code,
          error_msg: lastError?.message || null,
          extra_context: {
            source: 'strategy_lab',
            traceback: lastError?.traceback || null,
          },
          history: history.slice(-8).map((h) => ({ role: h.role, content: h.content })),
        }),
      });

      if (!resp.ok || !resp.body) {
        const text = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const raw of lines) {
          const line = raw.trim();
          if (!line.startsWith('data:')) continue;
          const payload = line.slice(5).trim();
          if (!payload || payload === '[DONE]') continue;
          try {
            const obj = JSON.parse(payload);
            if (obj.delta) {
              setHistory((h: ChatTurn[]) => {
                const out = [...h];
                const last = out[out.length - 1];
                if (last && last.role === 'assistant') {
                  last.content += obj.delta;
                }
                return out;
              });
            } else if (obj.error) {
              const human = humanizeError(obj.error, '');
              setHistory((h: ChatTurn[]) => {
                const out = [...h];
                const last = out[out.length - 1];
                if (last && last.role === 'assistant') {
                  last.content = `❌ ${human.title}\n${human.hint || ''}\n\n${obj.error}`;
                }
                return out;
              });
            }
          } catch {
            /* ignore stray non-JSON lines */
          }
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        const human = humanizeError(String(e?.message || e), '');
        message.error(`AI 助手失败: ${human.title}`);
        setHistory((h: ChatTurn[]) => {
          const out = [...h];
          const last = out[out.length - 1];
          if (last && last.role === 'assistant') {
            last.content = `❌ ${human.title}\n${human.hint || ''}\n\n${String(e?.message || e)}`;
          }
          return out;
        });
      }
    } finally {
      setBusy(false);
      setHistory((h: ChatTurn[]) => {
        const out = [...h];
        const last = out[out.length - 1];
        if (last && last.role === 'assistant') last.streaming = false;
        return out;
      });
      cancelRef.current = null;
    }
  }, [busy, code, history, lastError]);

  const handleApply = useCallback((turn: ChatTurn) => {
    const fenced = extractFencedPython(turn.content);
    if (!fenced) {
      message.warning('该回复中没有可识别的 ```python 代码块');
      return;
    }
    Modal.confirm({
      title: '替换编辑器内容？',
      content: '将以这段 AI 给出的代码覆盖当前脚本。可以先复制原代码做备份。',
      okText: '替换',
      cancelText: '取消',
      onOk: () => {
        onApplyCode(fenced);
        message.success('已应用到编辑器');
      },
    });
  }, [onApplyCode]);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={
        <span>
          <RobotOutlined /> AI 助手 <Tag color="blue">Sprint 2 · Day 8/9</Tag>
        </span>
      }
      width={460}
      mask={false}
      destroyOnClose={false}
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div
          ref={scrollRef}
          style={{ flex: 1, overflowY: 'auto', padding: '4px 4px 12px', minHeight: 0 }}
        >
          {history.length === 0 ? (
            <div>
              <Empty description="问点什么？AI 知道当前编辑器里的代码与最近的报错。" />
              <div style={{ marginTop: 12 }}>
                <Text strong style={{ fontSize: 12 }}>常用提问：</Text>
                <ul style={{ paddingLeft: 18, marginTop: 6, fontSize: 12 }}>
                  {SUGGESTED_PROMPTS.map((p, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>
                      <Button
                        size="small"
                        type="link"
                        style={{ padding: 0, height: 'auto', textAlign: 'left', whiteSpace: 'normal' }}
                        onClick={() => send(p)}
                      >
                        {p}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            history.map((turn, i) => (
              <div
                key={i}
                style={{
                  marginBottom: 10,
                  padding: 10,
                  borderRadius: 8,
                  background: turn.role === 'user' ? '#e6f4ff' : '#f4f4f5',
                }}
              >
                <Text strong style={{ fontSize: 11, color: '#64748b' }}>
                  {turn.role === 'user' ? '你' : 'AI 助手'}
                  {turn.streaming && <Tag color="processing" style={{ marginLeft: 6 }}>生成中…</Tag>}
                </Text>
                <Paragraph
                  style={{ margin: '4px 0 4px', whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.5 }}
                  copyable={turn.role === 'assistant' && !turn.streaming}
                >
                  {turn.content || (turn.streaming ? '…' : '')}
                </Paragraph>
                {turn.role === 'assistant' && !turn.streaming && extractFencedPython(turn.content) && (
                  <Tooltip title="将 ```python 代码块替换到编辑器">
                    <Button size="small" icon={<CodeOutlined />} onClick={() => handleApply(turn)}>
                      应用到编辑器
                    </Button>
                  </Tooltip>
                )}
              </div>
            ))
          )}
        </div>

        <div style={{ borderTop: '1px solid #eee', paddingTop: 8 }}>
          <TextArea
            rows={3}
            value={input}
            placeholder="例：把 universe 换成 csi500，加 RSI 超卖反弹"
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
          />
          <Space style={{ marginTop: 6, width: '100%', justifyContent: 'space-between' }}>
            <Text type="secondary" style={{ fontSize: 11 }}>
              Shift+Enter 换行，Enter 发送
            </Text>
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={busy}
              onClick={() => send(input)}
              disabled={!input.trim()}
            >
              发送
            </Button>
          </Space>
        </div>
      </div>
    </Drawer>
  );
};

export default StrategyLabAiDrawer;
