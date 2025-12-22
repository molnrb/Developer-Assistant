import useProjectStore from "../state/ProjectStore";
import useAuthStore from "../state/useAuthStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export async function saveCurrentProject() {
  const { token } = useAuthStore.getState();
  const project = useProjectStore.getState().project;
  if (!project) throw new Error("No project in store");
  console.log("numbre of files to save:", project.files.length); 

  const payload = {
    id: project.id,
    title: project.title ?? "Untitled Project",
    files: project.files.map(f => ({ name: f.name, content: f.content })),
    messages: project.messages.map(m => ({
      id: m.id,
      content: m.content,
      fromUser: m.fromUser,
    })),
  };

  const res = await fetch(`${API_BASE_URL}/database/add_project`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Save failed: ${res.status} ${text}`);
  }
}
