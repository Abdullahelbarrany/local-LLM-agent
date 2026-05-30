import { useCallback, useEffect, useRef, useState } from "react";

export interface WsEvent {
  type: string;
  [key: string]: unknown;
}

export function useWebSocket(path: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<WsEvent[]>([]);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}://${host}${path}`);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data) as WsEvent;
        setEvents((prev) => [...prev, evt]);
      } catch {
        // ignore malformed frames
      }
    };

    wsRef.current = ws;
  }, [path]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  const send = useCallback((payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { send, events, connected, clearEvents };
}
