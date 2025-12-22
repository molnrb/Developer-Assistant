import useProjectStore from "../state/ProjectStore";
import type { NormalizedProject } from "../services/ProjectLoader";

export function applyProjectToStore(p: NormalizedProject) {
  const store = useProjectStore.getState();
  store.setFiles(p.files);
  store.setActiveFile(p.files[0]?.name ?? null);
  store.renameProject(p.title);
  store.setId(p.id);
  store.setMessages(p.messages);
  store.setReady(true);
}
