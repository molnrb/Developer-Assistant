  import { useMutation } from "@tanstack/react-query";
  import useAuthStore from "../state/useAuthStore";

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


  type DownloadResult = {
    blob: Blob;
    filename: string;
    objectUrl: string; 
  };

  function parseFilenameFromContentDisposition(header?: string | null): string | null {
    if (!header) return null;
    const filenameStar = /filename\*=\s*[^']+'[^']*'([^;]+)/i.exec(header);
    if (filenameStar?.[1]) return decodeURIComponent(filenameStar[1]);
    const filename = /filename=\s*"([^"]+)"|filename=\s*([^;]+)/i.exec(header);
    return filename?.[1] ?? filename?.[2] ?? null;
  }

  export function downloadBlob(blob: Blob, filename = "download.bin") {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  type Options = { baseUrl?: string };

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  export function useDownloadArtifact(_opts: Options = {}) {
    const mutation = useMutation<DownloadResult, Error, string>({
      mutationFn: async (runId: string) => {
        const { token } = useAuthStore.getState(); 
        const res = await fetch(`${API_BASE_URL}/runs/${runId}/artifact.zip`, {
          headers: { Authorization: `Bearer ${token ?? ""}` },
        });
        if (!res.ok) {
          throw new Error(`Artifact download failed: HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const cd = res.headers.get("Content-Disposition");
        const filename = parseFilenameFromContentDisposition(cd) ?? `run-${runId}.zip`;
        const objectUrl = URL.createObjectURL(blob);
        return { blob, filename, objectUrl };
      },
    });

    return {
      ...mutation,
      downloadAndSave: async (runId: string) => {
        const res = await mutation.mutateAsync(runId);
        downloadBlob(res.blob, res.filename);
        return res;
      },
    };
  }
