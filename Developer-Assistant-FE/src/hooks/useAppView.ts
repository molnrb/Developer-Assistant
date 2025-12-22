import { useMemo } from "react";
import { useRunStore } from "../state/runStore";
import useProjectStore from "../state/ProjectStore";

export type AppView = "new" | "run" | "shell";

export function useAppView(): AppView {
  const running = useRunStore(s => s.running);
  const ready = useProjectStore(s => s.ready);

  return useMemo(() => {
    if (running) return "run";
    if (ready)   return "shell";
    return "new";
  }, [running, ready]);
}
