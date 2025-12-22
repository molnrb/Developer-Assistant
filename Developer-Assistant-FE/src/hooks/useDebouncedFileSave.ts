import { useMutation } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef } from "react";
import useProjectStore from "../state/ProjectStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


async function patchFileContent({
  projectId,
  fileName,
  content,
  token,
}: {
  projectId: string;
  fileName: string;
  content: string;
  token?: string;
}) {
  const res = await fetch(`${API_BASE_URL}/database/projects/${encodeURIComponent(projectId)}/files`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ name: fileName, content }),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => "");
    throw new Error(msg || `Failed to update file content (${res.status})`);
  }
}


function stripTwBuilt(html: string): string {
  if (!html) return html;
  return html.replace(
    /<style[^>]*\bid\s*=\s*["']tw-built["'][^>]*>[\s\S]*?<\/style>/i,
    ""
  );
}

export function useDebouncedFileSave({
  projectId,
  fileName,
  delayMs = 1200,
  token,
}: {
  projectId: string;
  fileName: string;
  delayMs?: number;
  token?: string;
}) {
  const setIsPending = useProjectStore((s) => s.setIsPending);
  const updateFile = useProjectStore((s) => s.updateFile);

  const key = useMemo(() => `${projectId}::${fileName}`, [projectId, fileName]);
  const latestContentRef = useRef<string>("");
  const prevContentRef = useRef<string>("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    latestContentRef.current = "";
    prevContentRef.current = "";
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, [key]);

  const mutation = useMutation({
    mutationFn: async () => {
      const raw = latestContentRef.current ?? "";
      const contentToSave =
        fileName && fileName.endsWith("index.html") ? stripTwBuilt(raw) : raw;

      return patchFileContent({
        projectId,
        fileName,
        content: contentToSave,
        token,
      });
    },
    onMutate: () => setIsPending(true),
    onError: () => {
      if (prevContentRef.current) updateFile(fileName, prevContentRef.current);
      console.error("Failed to save file changes.");
    },
    onSettled: () => setIsPending(false),
  });

  const save = useCallback(
    (content: string) => {
      if (!projectId || !fileName) return;
      if (!prevContentRef.current) {
        const current =
          useProjectStore
            .getState()
            .project?.files.find((f) => f.name === fileName)?.content ?? "";
        prevContentRef.current = current;
      }
      latestContentRef.current = content;
      updateFile(fileName, content);

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => mutation.mutate(), delayMs);
    },
    [projectId, fileName, delayMs, mutation, updateFile]
  );

  const flush = useCallback(() => {
    if (!projectId || !fileName) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    mutation.mutate();
  }, [projectId, fileName, mutation]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return { save, flush, isSaving: mutation.isPending, error: mutation.error as Error | null };
}
