import { useMutation, UseMutationOptions, useQueryClient } from '@tanstack/react-query';
import useAuthStore from '../state/useAuthStore';
import useProjectStore from '../state/ProjectStore';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

type Json = Record<string, unknown>;

async function apiFetch<T>(
  path: string,
  init?: RequestInit & { json?: Json }
): Promise<T> {
  const { json, headers, method, ...rest } = init ?? {};

  const { token } = useAuthStore.getState();

  const alreadyHasAuth =
    !!(headers as Record<string, unknown> | undefined)?.['Authorization'] ||
    !!(headers as Headers | undefined instanceof Headers && (headers as Headers).get?.('Authorization'));

  const authHeader =
    !alreadyHasAuth && token ? { Authorization: `Bearer ${token}` } : {};

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: method ?? 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader,
      ...(headers || {}),
    } as HeadersInit,
    body: json ? JSON.stringify(json) : undefined,
    ...rest,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  const ct = res.headers.get('content-type') ?? '';
  if (!ct.includes('application/json')) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const projectKey = (projectId: string) => ['project', projectId] as const;
export const projectFilesKey = (projectId: string) => ['project', projectId, 'files'] as const;

export type AddFilePayload = {
  name: string;
  content: string;
};

export type DeleteFilePayload = {
  name: string;
};

export type RenameProjectPayload = {
  title: string;
};

export function useDeleteFile(
  projectId: string,
  options?: UseMutationOptions<unknown, Error, DeleteFilePayload>
) {
  const qc = useQueryClient();
  return useMutation<unknown, Error, DeleteFilePayload>({
    mutationFn: (payload) =>
      apiFetch<unknown>(`/database/projects/${encodeURIComponent(projectId)}/files/delete`, {
        json: payload,
      }),
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: projectFilesKey(projectId) });
      qc.invalidateQueries({ queryKey: projectKey(projectId) });
      options?.onSuccess?.(data, vars, ctx as unknown);
    },
    onError: options?.onError,
    onSettled: options?.onSettled,
  });
}

export function useAddFile(
  projectId: string,
  options?: UseMutationOptions<unknown, Error, AddFilePayload>
) {
  const qc = useQueryClient();
  return useMutation<unknown, Error, AddFilePayload>({
    mutationFn: (payload) =>
      apiFetch<unknown>(`/database/projects/${encodeURIComponent(projectId)}/files/add`, {
        json: payload,
      }),
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: projectFilesKey(projectId) });
      qc.invalidateQueries({ queryKey: projectKey(projectId) });
      options?.onSuccess?.(data, vars, ctx as unknown);
    },
    onError: options?.onError,
    onSettled: options?.onSettled,
  });
}

export function useRenameProject(
  projectId: string,
  options?: UseMutationOptions<unknown, Error, RenameProjectPayload>
) {
  const qc = useQueryClient();
  return useMutation<unknown, Error, RenameProjectPayload>({
    mutationFn: (payload) =>
      apiFetch<unknown>(`/projects/${encodeURIComponent(projectId)}/rename_project`, {
        json: payload,
      }),
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: projectKey(projectId) });
      options?.onSuccess?.(data, vars, ctx as unknown);
    },
    onError: options?.onError,
    onSettled: options?.onSettled,
  });
}

type ProjectListItem = {
  id: string;
  title?: string;
  updatedAt?: string;
};

type DeleteProjectContext = {
  previousProjects?: ProjectListItem[];
};

export function useDeleteProject(
  options?: UseMutationOptions<unknown, Error, string, DeleteProjectContext>
) {
  const qc = useQueryClient();
  const { resetProject} = useProjectStore();
  return useMutation<unknown, Error, string, DeleteProjectContext>({
    mutationFn: (projectId: string) =>
      apiFetch<unknown>(
        `/database/delete_project/${encodeURIComponent(projectId)}`,
        { method: 'DELETE' }
      ),

    async onMutate(projectId) {
      await qc.cancelQueries({ queryKey: ['projects'] });

      const previousProjects = qc.getQueryData<ProjectListItem[]>(['projects']);

      qc.setQueryData<ProjectListItem[]>(['projects'], (old) =>
        old ? old.filter((p) => p.id !== projectId) : old
      );

      options?.onMutate?.(projectId);

      return { previousProjects };
    },

    onError(error, projectId, context) {
      if (context?.previousProjects) {
        qc.setQueryData<ProjectListItem[]>(['projects'], context.previousProjects);
      }
      options?.onError?.(error, projectId, context);
    },

    onSuccess(data, projectId, context) {
      resetProject();
      qc.invalidateQueries({ queryKey: projectKey(projectId) });
      qc.invalidateQueries({ queryKey: ['projects'] });
      options?.onSuccess?.(data, projectId, context);
    },

    onSettled(data, error, projectId, context) {
      options?.onSettled?.(data, error, projectId, context);
    },
  });
}