/**
 * TypeScript types for real-time WebSocket communication in Phase 10.
 * Directly aligns with backend Pydantic contracts in app/models/realtime.py.
 */

export type RealtimeMessageType =
  | 'event_created'
  | 'trace_started'
  | 'trace_completed';

export interface RealtimeEventPayload {
  event_id: string;
  trace_id: string;
  event_type: string;
  timestamp: string;
  parent_event_id: string | null;
  data: Record<string, unknown>;
  metadata: Record<string, unknown>;
  depth?: number | null;
  duration_ms?: number | null;
}

export interface EventCreatedMessage {
  type: 'event_created';
  trace_id: string;
  event: RealtimeEventPayload;
}

export interface TraceStartedMessage {
  type: 'trace_started';
  trace_id: string;
  name: string;
  project_name: string | null;
  start_time: string;
  status: string;
}

export interface TraceCompletedMessage {
  type: 'trace_completed';
  trace_id: string;
  status: string;
  end_time: string | null;
  duration_ms: number | null;
}

export type RealtimeMessage =
  | EventCreatedMessage
  | TraceStartedMessage
  | TraceCompletedMessage;

export type RealtimeConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'error';
