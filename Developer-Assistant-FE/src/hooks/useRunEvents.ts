import { useEffect, useRef } from "react";
import { useRunStore } from "../state/runStore";
import type { RunEvent } from "../types/run-events";
import useAuthStore from '../state/useAuthStore';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


export function useRunEvents(runId?: string) {
  const pushEvent = useRunStore(s => s.pushEvent);
  const esRef = useRef<EventSource | null>(null);
  const token = useAuthStore((state) => state.token);

  useEffect(() => {
    if (!runId) return;

    const url = `${API_BASE_URL}/runs/${encodeURIComponent(runId)}/events?token=${encodeURIComponent(token ?? '')}`;
    const es = new EventSource(url, { withCredentials: false });
    esRef.current = es;

    es.onopen = () => console.info("[SSE] open", url);
    es.onmessage = (msg) => {
      try {
        const e: RunEvent = JSON.parse(msg.data);
        pushEvent(e);
      } catch (err) {
        console.warn("[SSE] non-JSON", msg.data);
        console.error(err);
      }
    };
    es.onerror = (ev) => console.error("[SSE] error", ev);

    return () => {
      es.close();
      esRef.current = null;
      console.info("[SSE] closed");
    };
  }, [pushEvent, runId, token]);
}
