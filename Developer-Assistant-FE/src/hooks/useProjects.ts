import { useQuery } from "@tanstack/react-query";
import useAuthStore from "../state/useAuthStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export interface ProjectResponse {
  id: string;
  title: string;
}

export function useProjects(enabled: boolean = true) {
  const token = useAuthStore((state) => state.token);

  const fetchProjects = async (): Promise<ProjectResponse[]> => {
    const res = await fetch(`${API_BASE_URL}/database/get_projects`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) throw new Error("Failed to fetch projects");

    const data = await res.json();
    return data.projects;
  };

  const query = useQuery<ProjectResponse[]>({
    queryKey: ["projects"],
    queryFn: fetchProjects,
    enabled: enabled && !!token,
    refetchOnWindowFocus: false,
    retry: 2,
    retryDelay: attempt => Math.min(1000 * 2 ** attempt, 3000),
  });

  return {
    ...query,
    projects: query.data ?? [],
  };
}
