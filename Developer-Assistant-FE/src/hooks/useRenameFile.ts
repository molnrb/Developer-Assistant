import { useMutation, useQueryClient } from "@tanstack/react-query";
import useProjectStore from "../state/ProjectStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


async function patchRenameFile({
  projectId,
  oldName,
  newName,
  token,
}: {
  projectId: string;
  oldName: string;
  newName: string;
  token?: string;
}) {
  const authToken = token ?? localStorage.getItem("token") ?? "";
  const res = await fetch(`${API_BASE_URL}/database/projects/${encodeURIComponent(projectId)}/files/rename`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: JSON.stringify({ old_name: oldName, new_name: newName }),
  });
  if (!res.ok) throw new Error(await res.text().catch(() => "Failed to rename file"));
}


export function useRenameFile(opts: { projectId: string; token?: string }) {
  const { projectId, token } = opts;
  const qc = useQueryClient();
  const setFiles = useProjectStore((s) => s.setFiles);
  const setActiveFile = useProjectStore((s) => s.setActiveFile);
  const getProject = useProjectStore((s) => s.getProject);

  const mutation = useMutation({
    mutationFn: ({ oldName, newName }: { oldName: string; newName: string }) =>
      patchRenameFile({ projectId, oldName, newName, token }),
    onMutate: async ({ oldName, newName }) => {
      await qc.cancelQueries({ queryKey: ["project", projectId] });
      const project = getProject();
      if (!project) throw new Error("No active project");
      if (project.files.some((f) => f.name === newName)) {
        throw new Error("File with the new name already exists");
      }
      const nextFiles = project.files.map((f) =>
        f.name === oldName ? { ...f, name: newName } : f
      );
      setFiles(nextFiles);
      if (project.activeFile === oldName) setActiveFile(newName);
      return { prevFiles: project.files, prevActive: project.activeFile };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prevFiles) setFiles(ctx.prevFiles);
      if (ctx?.prevActive !== undefined) setActiveFile(ctx.prevActive ?? null);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["project", projectId], exact: true });
    },
  });

  return {
    renameFile: mutation.mutate,
    renameFileAsync: mutation.mutateAsync,
    isRenaming: mutation.isPending,
    error: mutation.error as Error | null,
  };
}
