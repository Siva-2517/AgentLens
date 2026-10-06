import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RealtimeClient } from '../services/realtime';
import {
  RealtimeMessage,
  RealtimeConnectionState,
} from '../types/realtime';

// Mock WebSocket implementation for Vitest
class MockWebSocket {
  public static instances: MockWebSocket[] = [];
  public readyState: number = WebSocket.CONNECTING;
  public url: string;
  public onopen: (() => void) | null = null;
  public onmessage: ((e: { data: string }) => void) | null = null;
  public onerror: (() => void) | null = null;
  public onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) this.onopen();
    }, 10);
  }

  public send = vi.fn();
  public close = vi.fn((_code?: number, _reason?: string) => {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose();
  });
}

describe('RealtimeClient Service', () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    MockWebSocket.instances = [];
    originalWebSocket = globalThis.WebSocket;
    // @ts-expect-error Mocking global WebSocket
    globalThis.WebSocket = MockWebSocket;
    vi.useFakeTimers();
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('connects to the WebSocket with the proper URL and token', () => {
    const stateChanges: RealtimeConnectionState[] = [];
    const client = new RealtimeClient({
      traceId: 'tr_test_123',
      apiKey: 'secret_key_456',
      wsBaseUrl: 'ws://localhost:8000/api/v1/ws/traces',
      onStateChange: (st) => stateChanges.push(st),
      onMessage: vi.fn(),
    });

    client.connect();
    expect(stateChanges).toContain('connecting');

    // Advance timer for open event
    vi.advanceTimersByTime(20);

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe(
      'ws://localhost:8000/api/v1/ws/traces/tr_test_123?token=secret_key_456'
    );
    expect(stateChanges).toContain('connected');
  });

  it('receives and parses valid real-time messages', () => {
    const receivedMessages: RealtimeMessage[] = [];
    const client = new RealtimeClient({
      traceId: 'tr_test_123',
      onStateChange: vi.fn(),
      onMessage: (msg) => receivedMessages.push(msg),
    });

    client.connect();
    vi.advanceTimersByTime(20);

    const ws = MockWebSocket.instances[0];
    const incoming: RealtimeMessage = {
      type: 'event_created',
      trace_id: 'tr_test_123',
      event: {
        event_id: 'e1',
        trace_id: 'tr_test_123',
        event_type: 'LLM_CALL',
        timestamp: '2026-01-01T12:00:00Z',
        parent_event_id: null,
        data: {},
        metadata: {},
      },
    };

    ws.onmessage?.({ data: JSON.stringify(incoming) });

    expect(receivedMessages).toHaveLength(1);
    expect(receivedMessages[0]).toEqual(incoming);
  });

  it('ignores malformed messages gracefully', () => {
    const onMessageMock = vi.fn();
    const client = new RealtimeClient({
      traceId: 'tr_test_123',
      onStateChange: vi.fn(),
      onMessage: onMessageMock,
    });

    client.connect();
    vi.advanceTimersByTime(20);

    const ws = MockWebSocket.instances[0];
    ws.onmessage?.({ data: 'NOT_VALID_JSON{[' });

    expect(onMessageMock).not.toHaveBeenCalled();
  });

  it('handles clean disconnect without reconnecting', () => {
    const stateChanges: RealtimeConnectionState[] = [];
    const client = new RealtimeClient({
      traceId: 'tr_test_123',
      onStateChange: (st) => stateChanges.push(st),
      onMessage: vi.fn(),
    });

    client.connect();
    vi.advanceTimersByTime(20);

    client.disconnect();
    expect(stateChanges[stateChanges.length - 1]).toBe('disconnected');

    // Advance time - should NOT attempt reconnection
    vi.advanceTimersByTime(10000);
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('schedules reconnection with exponential backoff on unexpected disconnect', () => {
    const stateChanges: RealtimeConnectionState[] = [];
    const client = new RealtimeClient({
      traceId: 'tr_test_123',
      onStateChange: (st) => stateChanges.push(st),
      onMessage: vi.fn(),
      maxRetries: 3,
    });

    client.connect();
    vi.advanceTimersByTime(20);

    const ws = MockWebSocket.instances[0];
    // Unexpected close
    ws.close();

    expect(stateChanges).toContain('disconnected');
    expect(client.getRetryCount()).toBe(1);

    // Fast-forward backoff delay (1s)
    vi.advanceTimersByTime(1050);
    expect(MockWebSocket.instances).toHaveLength(2);
  });
});
