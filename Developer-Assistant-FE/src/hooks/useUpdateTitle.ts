import { useMutation } from '@tanstack/react-query';
import useAuthStore from '../state/useAuthStore';
import useProjectStore from '../state/ProjectStore';
import { toast } from 'react-toastify';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


export function useUpdateTitle() {
  const token = useAuthStore((s) => s.token);
  const getProjectStore = useProjectStore;

  return useMutation({
    mutationFn: async (newTitle: string): Promise<void> => {
      const { project } = getProjectStore.getState();

      if (!project) {
        throw new Error('❌ No project selected to save.');
      }

      console.log('📦 Saving project:', project.id);

      const response = await fetch(`${API_BASE_URL}/database/update_project_title/${project.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: newTitle
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`❌ Failed to save project: ${text}`);
      }
    },
    onSuccess: () => {
      
    },
    onError: (error: Error) => {
      toast.error(`🚨 Mentés sikertelen: ${error.message}`);
    },
  });
}
