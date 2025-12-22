import { useMutation } from "@tanstack/react-query";
import useAuthStore from "../state/useAuthStore";
import { useRunStore } from "../state/runStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export interface KillRunResponse {
  ok: boolean;
  kill_requested: boolean;
}

export function useKillRun() {
  const token = useAuthStore((state) => state.token);
  const { reset } = useRunStore();

  const mutation = useMutation<KillRunResponse, Error, string>({
    mutationFn: async (runId: string): Promise<KillRunResponse> => {
      if (!token) {
        throw new Error("No auth token available");
      }

      const res = await fetch(`${API_BASE_URL}/runs/${runId}/kill`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Failed to kill run: ${text}`);
      }

      return res.json();
    },
    onSuccess: () => {
      reset();
    }
  });

  return {
    ...mutation,
    killRun: mutation.mutate,  
    killRunAsync: mutation.mutateAsync, 
  };
}
