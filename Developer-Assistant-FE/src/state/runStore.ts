import { create } from "zustand";
import { devtools, subscribeWithSelector } from "zustand/middleware";
import useProjectStore from "./ProjectStore"; 
import { RunEvent } from "../types/run-events";
import { fetchProjectDirect } from "../services/ProjectLoader";
import { normalizeProject } from "../services/ProjectLoader";
import { applyProjectToStore } from "./applyProject";
import { Message } from "./ProjectStore";

type StepState = "queued" | "running" | "done" | "failed";
type RunType = "generate" | "modify";
type DoneEvent = { t: "done"; projectId?: string; project_id?: string };

let doneInflight = false; 

interface RunState {
  runId?: string;
  running: boolean;
  runType?: RunType;
  steps: Record<string, StepState>;
  logs: Message[];
  last?: RunEvent;

  setRunId: (id: string) => void;
  getStep: (step: string) => string |  undefined;
  setRunType: (runType: RunType) => void;
  setRunning: (running: boolean) => void;
  appendLog: (line: string, fromUser: boolean) => void;
  setStep: (step: string, state: StepState) => void;
  pushEvent: (e: RunEvent) => void;
  reset: () => void;
  initRun: (runId: string, runType: RunType) => void;
}

const initialRunState: Omit<RunState, "appendLog" | "setStep" | "pushEvent" | "reset" | "setRunId" | "setRunType" | "setRunning" | "getStep" | "initRun" > = {
  runId: undefined,
  running: false,
  steps: {},
  logs: [],
  last: undefined,
};

export const useRunStore = create<RunState>()(
  subscribeWithSelector(
    devtools((set, get) => ({
      ...initialRunState,

      reset: () => {
        doneInflight = false;
        set(initialRunState);
      },

      initRun: (runId, runType) => {
        doneInflight = false;
        set({
           ...initialRunState,
           runId,
           runType,
           running: true,
           steps: { router: "queued" }
        });
      },

      appendLog: (line, fromUser) =>
        set((s) => ({
          logs: [...s.logs, {id: s.logs.length + 1, content: line, fromUser: fromUser}],
        })),

      setRunId: (id) => set({ runId: id }),

      setRunType: (runType) => set({ runType }),

      getStep: (step) => get().steps[step],

      setStep: (step, state) =>
        set((s) => ({ steps: { ...s.steps, [step]: state } })),

      setRunning: (running) => set({ running }),

      pushEvent: (e) => {
        console.log("Run Event:", e);
        if (e.t === "status" && typeof e.step === "string") get().setStep(e.step, e.state as StepState);

        if (e.t === "log") {
          const line = typeof e.chunk === "string" ? e.chunk : "";
          get().appendLog(line, false);
        }
        if (e.t === "title.generated") {
          const projectStore = useProjectStore.getState();
          projectStore.renameProject(typeof e.title === "string" ? e.title : "Untitled Project");
        }
        if (e.t === "done") {
          if (doneInflight) {
            return;
          }
          doneInflight = true;

          get().setStep("done", "done");

          const projectStore = useProjectStore.getState();
          projectStore.setReady(true);

          if (e.ok === false) {
            projectStore.addMessage("Pipeline failed to complete.", false);
            doneInflight = false;
            return;
          }

          (async () => {
            try {
              projectStore.setIsPending(true);

              const projectId = get().runId ?? (e as DoneEvent).projectId ?? (e as DoneEvent).project_id;
              if (!projectId) throw new Error("Missing projectId in 'done' event");

              const raw = await fetchProjectDirect(projectId);
              const normalized = normalizeProject(raw);

              applyProjectToStore(normalized);

            } catch (err: unknown) {
              console.error(err);
            } finally {
              projectStore.setIsPending(false);
              doneInflight = false;
            }
          })();
          set({ running: false });
        }

        set({ last: e });
      },
    }))
  )
);