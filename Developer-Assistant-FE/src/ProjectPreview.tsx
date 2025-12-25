import { useEffect, useRef, useState, useCallback } from "react";
import useAuthStore from "./state/useAuthStore";

type Props = {
  runId: string;
};

export function ProjectPreview({ runId }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isReloading, setIsReloading] = useState(false);

  const token = useAuthStore((state) => state.token);
  const lastRunIdRef = useRef<string | null>(null);

  const handleReload = useCallback(() => {
    if (!runId || !token) return;

    setIsReloading(true);
    setError(null);

    fetch(`http://localhost:8000/preview/${runId}/reload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data: { url: string; port: number }) => {
        setUrl(data.url);
      })
      .catch((err) => setError(err.message))
      .finally(() => setIsReloading(false));
  }, [runId, token]);

  useEffect(() => {
    if (!runId || !token) return;

    if (lastRunIdRef.current === runId && url) {
      return;
    }

    lastRunIdRef.current = runId;
    setLoading(true);
    setError(null);

    fetch(`http://localhost:8000/preview/${runId}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data: { url: string; port: number }) => {
        setUrl(data.url);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [runId, token, url]);


  if (loading) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-transparent">
        <div className="mb-4 h-10 w-10 animate-spin rounded-full border-4 border-white/30 border-t-white" />
        <div className="text-lg font-medium text-white animate-pulse">
          Loading your project...
        </div>
      </div>
    );
  }

  if (error) {
    return <div className="p-4 text-xs text-red-500">Error: {error}</div>;
  }

  if (!url) return null;

  return (
    <div className="relative w-full h-full">
      <button
        type="button"
        onClick={handleReload}
        className="absolute bottom-4 right-4 z-10 w-12 h-12 rounded-full 
                   bg-white text-black shadow-lg
                   flex items-center justify-center text-xl
                   hover:bg-gray-200 hover:scale-105 transition-all duration-200"
        title="Reload preview"
      >
        {isReloading ? (
          <span className="inline-block w-5 h-5 border-2 border-gray-300 border-t-gray-800 rounded-full animate-spin" />
        ) : (
          "↻"
        )}
      </button>

      <iframe
        key={url}
        src={url}
        className="w-full h-full border-0"
        title="Live preview"
      />
    </div>
  );
}