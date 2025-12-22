import Header from "./components/Header";
import { NewRun } from "./newRun";
import { RunShell } from "./RunShell";
import { RunView } from "./runView";
import { useRunStore } from "./state/runStore";

import { useAppView } from "./hooks/useAppView";
import { newProject, startGeneration } from "./hooks/appController";

export default function MainLayout() {
  const runId = useRunStore(s => s.runId); 
  const runType = useRunStore(s => s.runType);
  const view = useAppView();

  return (
    <div className="h-dvh flex flex-col">
      <Header 
        runId={runId}
        onNewProject={() => newProject("Undefined Project")}
      />

      <main className="flex-1 overflow-hidden">
        {view === "new"  && (
          <NewRun
            onReady={(rid) => {
              startGeneration(rid);
            }}
          />
        )}

        {view === "run"  && <RunView runType={runType} />}

        {view === "shell" && <RunShell />}
      </main>
    </div>
  );
}
