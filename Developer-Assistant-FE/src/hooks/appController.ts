import { useRunStore } from "../state/runStore";
import useProjectStore from "../state/ProjectStore";

export const newProject = (title = "New Project") => {
  const run = useRunStore.getState();
  const proj = useProjectStore.getState();
  run.reset();
  proj.resetProject(title); 
  run.setRunning(false);
};

export const startGeneration = (runId: string) => {
  const run = useRunStore.getState();
  const proj = useProjectStore.getState();
  run.reset();
  proj.resetProject("Generating…"); 
  run.setRunId(runId);
  run.setRunning(true);
};

export const finishGeneration = () => {
  const run = useRunStore.getState();
  run.setRunning(false);
};
