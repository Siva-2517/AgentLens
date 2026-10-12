import {
  RealtimeMessage,
  RealtimeConnectionState,
} from '../types/realtime';

export interface RealtimeClientOptions {
  traceId: string;
  apiKey?: string;
  wsBaseUrl?: string;
  onMessage: (message: RealtimeMessage) => void;
  onStateChange: (state: RealtimeConnectionState) => void;
  maxRetries?: number;
}

export class RealtimeClient {
  private traceId: string;
  private apiKey: string;
  private wsBaseUrl: string;
  private onMessage: (message: RealtimeMessage) => void;
  private onStateChange: (state: RealtimeConnectionState) => void;
  private maxRetries: number;

  private socket: WebSocket | null = null;
  private retryCount = 0;
  private isIntentionallyClosed = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(options: RealtimeClientOptions) {
    this.traceId = options.traceId;
    this.apiKey = options.apiKey || '';

    // Construct WebSocket URL dynamically from env or window.location
    if (options.wsBaseUrl) {
      this.wsBaseUrl = options.wsBaseUrl;
    } else if (import.meta.env.VITE_WS_BASE_URL) {
      this.wsBaseUrl = import.meta.env.VITE_WS_BASE_URL as string;
    } else if (import.meta.env.VITE_API_BASE_URL && String(import.meta.env.VITE_API_BASE_URL).startsWith('http')) {
      const apiUrl = new URL(String(import.meta.env.VITE_API_BASE_URL));
      const wsProto = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
      this.wsBaseUrl = `${wsProto}//${apiUrl.host}${apiUrl.pathname.replace(/\/$/, '')}/ws/traces`;
    } else if (typeof window !== 'undefined' && window.location) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.port === '5173' ? `${window.location.hostname}:8000` : window.location.host;
      this.wsBaseUrl = `${protocol}//${host}/api/v1/ws/traces`;
    } else {
      this.wsBaseUrl = '/api/v1/ws/traces';
    }

    this.onMessage = options.onMessage;
    this.onStateChange = options.onStateChange;
    this.maxRetries = options.maxRetries ?? 5;
  }

  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.onStateChange('connecting');

    const tokenParam = this.apiKey ? `?token=${encodeURIComponent(this.apiKey)}` : '';
    const url = `${this.wsBaseUrl}/${encodeURIComponent(this.traceId)}${tokenParam}`;

    try {
      this.socket = new WebSocket(url);
    } catch {
      this.onStateChange('error');
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.retryCount = 0;
      this.onStateChange('connected');
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        if (event.data === 'pong') return;
        const parsed = JSON.parse(event.data) as RealtimeMessage;
        if (parsed && typeof parsed.type === 'string') {
          this.onMessage(parsed);
        }
      } catch {
        // Skip malformed messages
      }
    };

    this.socket.onerror = () => {
      this.onStateChange('error');
    };

    this.socket.onclose = () => {
      this.socket = null;
      if (!this.isIntentionallyClosed) {
        this.onStateChange('disconnected');
        this.scheduleReconnect();
      } else {
        this.onStateChange('disconnected');
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.isIntentionallyClosed) return;
    if (this.retryCount >= this.maxRetries) {
      this.onStateChange('disconnected');
      return;
    }

    // Bounded exponential backoff: 1s, 2s, 4s, max 8s
    const delay = Math.min(1000 * Math.pow(2, this.retryCount), 8000);
    this.retryCount++;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectTimer = setTimeout(() => {
      if (!this.isIntentionallyClosed) {
        this.connect();
      }
    }, delay);
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      try {
        this.socket.close(1000, 'Client disconnected');
      } catch {
        // ignore
      }
      this.socket = null;
    }
    this.onStateChange('disconnected');
  }

  public getRetryCount(): number {
    return this.retryCount;
  }
}
