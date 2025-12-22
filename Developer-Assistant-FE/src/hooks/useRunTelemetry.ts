import { useQuery } from "@tanstack/react-query";
import useAuthStore from "../state/useAuthStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


export type RunTelemetry = {
  id: string;
  status: "passed" | "running";
  steps: unknown[];
  metrics: Record<string, unknown>;
  tokens: Record<string, unknown>;
  planCount: number;
  filesCount: number;
};

type Options = {
  enabled?: boolean;
  refetchMs?: number; 
  baseUrl?: string;   
};

export function useRunTelemetry(runId: string | null, opts: Options = {}) {
  const token = useAuthStore((s) => s.token);

  return useQuery<RunTelemetry>({
    queryKey: ["runs", "telemetry", runId],
    enabled: !!runId && (!!token) && (opts.enabled ?? true),
    queryFn: async () => {
      const res = await fetch(`${API_BASE_URL}/runs/${runId}/telemetry`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        let detail = "";
        try {
          const j = await res.json();
          detail = j?.detail ? ` (${j.detail})` : "";
        } catch { /* empty */ }
        throw new Error(`Telemetry fetch failed: HTTP ${res.status}${detail}`);
      }
      return res.json();
    },
    refetchInterval: (data) =>
      (((data as unknown) as RunTelemetry | undefined)?.status === "passed") ? false : (opts.refetchMs ?? 1500),
    refetchOnWindowFocus: false,
  });
}
