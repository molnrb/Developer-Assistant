import { useMutation } from "@tanstack/react-query";
import useProjectStore from "../state/ProjectStore";
import useAuthStore from "../state/useAuthStore";
{/*import { twBuiltCss } from "../util/twBuiltCss";*/}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

type FullProjectResponse = {
  id: string;
  title: string;
  files: { name: string; content: string | object }[];
  messages: { id: number; content: string; fromUser: boolean }[];
};

async function fetchProject(projectId: string): Promise<FullProjectResponse> {
  const { token } = useAuthStore.getState();
  const res = await fetch(`${API_BASE_URL}/database/get_project/${projectId}`, {
    headers: { Authorization: `Bearer ${token ?? ""}` },
  });
  if (!res.ok) {
    let detail = "";
    try { const d = await res.json(); detail = typeof d?.detail === "string" ? ` (${d.detail})` : ""; } catch { /* empty */ }
    throw new Error(`Failed to fetch project: HTTP ${res.status}${detail}`);
  }
  return res.json();
}

{/*function ensureInlineTw(html: string | undefined, css: string): string {
  const styleBlock = `<style id="tw-built">${css}</style>`;
  if (!html) {
    return `<!doctype html><html><head>${styleBlock}
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>App</title></head><body>
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
</body></html>`;
  }
  if (html.includes('id="tw-built"')) return html; 
  if (/<head[^>]*>/i.test(html)) {
    return html.replace(/<head[^>]*>/i, (m) => `${m}\n${styleBlock}`);
  }
  return `<!doctype html><html><head>${styleBlock}</head>${html.replace(/<!doctype html>/i, "").replace(/<html[^>]*>/i, "").replace(/<\/html>/i, "")}</html>`;
}*/}

export default function useFetchProject() {
  const getProjectStore = useProjectStore;

  const mutation = useMutation<FullProjectResponse, Error, string>({
    mutationFn: fetchProject,

    onMutate: () => getProjectStore.getState().setIsPending(true),

    onSuccess: (data) => {
      const store = getProjectStore.getState();
      if (!data) return;

      try {
        const files = (data.files ?? []).map((f) => {
          const content = typeof f.content === "object"
            ? JSON.stringify(f.content, null, 2)
            : (f.content ?? "");
          return { name: f.name, content };
        });

        {/*const idx = files.findIndex(f => f.name.endsWith("index.html"));
        if (idx >= 0) {
          files[idx] = { ...files[idx], content: ensureInlineTw(files[idx].content, twBuiltCss) };
        } else {
          files.push({ name: "index.html", content: ensureInlineTw(undefined, twBuiltCss) });
        }*/}

        store.setFiles(files);
        store.setActiveFile(files[0]?.name ?? null);
        store.renameProject(data.title);
        store.setId(data.id);
        store.setMessages(data.messages ?? []);
        store.setReady(true);
      } catch (e) {
        console.error("❌ Failed to apply project response:", e);
      }
    },

    onError: (error) => {
      console.error("❌ Error loading project:", error);
    },

    onSettled: () => getProjectStore.getState().setIsPending(false),
  });

  return {
    isPending: mutation.isPending,
    getProject: mutation.mutate,
    getProjectAsync: mutation.mutateAsync,
  };
}
