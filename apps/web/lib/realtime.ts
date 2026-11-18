"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export interface RealtimeEvent {
  event_id: string;
  event_type: string;
  occurred_at: string;
  resource_type: string;
  resource_id: string | null;
  data: Record<string, unknown>;
}

type Status = "idle" | "connecting" | "live" | "reconnecting" | "blocked";

interface Ticket {
  ticket: string;
  expires_in: number;
  path: string;
}

const MAX_EVENTS = 12;

/**
 * Short-lived ticket per connection: no cookie or token is placed in the socket URL
 * beyond a single-use value, and the server derives the organization from it.
 */
export function useRealtime(onEvent?: (event: RealtimeEvent) => void) {
  const [status, setStatus] = useState<Status>("idle");
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const handlerRef = useRef(onEvent);

  handlerRef.current = onEvent;

  const origin = process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8000";

  const connect = useCallback(async () => {
    try {
      setStatus((current) => (current === "live" ? current : "connecting"));
      const ticket = await api.post<Ticket>("/api/v1/realtime/ticket");
      const socket = new WebSocket(`${origin}${ticket.path}?ticket=${encodeURIComponent(ticket.ticket)}`);
      socketRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
        setStatus("live");
      };
      socket.onmessage = (message) => {
        try {
          const payload = JSON.parse(String(message.data)) as RealtimeEvent & { event_type: string };
          if (payload.event_type === "connected") {
            setStatus("live");
            return;
          }
          setEvents((current) => [payload, ...current].slice(0, MAX_EVENTS));
          handlerRef.current?.(payload);
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        socketRef.current = null;
        const attempt = retryRef.current + 1;
        retryRef.current = attempt;
        if (attempt > 5) {
          setStatus("blocked");
          return;
        }
        setStatus("reconnecting");
        setTimeout(() => void connect(), Math.min(attempt * 2000, 10000));
      };
      socket.onerror = () => {
        socket.close();
      };
    } catch {
      setStatus("blocked");
    }
  }, [origin]);

  useEffect(() => {
    void connect();
    return () => {
      const socket = socketRef.current;
      socketRef.current = null;
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
  }, [connect]);

  return { status, events };
}
