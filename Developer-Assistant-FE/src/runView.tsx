import { useMemo } from "react";
import { useRunStore } from "../src/state/runStore";
import { JSX } from "react/jsx-runtime";
import { Chat } from "./chat/Chat";
import { useRunEvents } from "./hooks/useRunEvents";

type StepKey = "router" | "planner" | "implement" | "test" | "fix";

const ALL_STEPS: StepKey[] = ["router", "planner", "implement", "test", "fix"];

export function RunView({ runType }: { runType?: string }) {
  const { steps, runId, logs } = useRunStore();
  useRunEvents(runId!);

  const stepOrder = useMemo<StepKey[]>(() => {
    if (runType === "modify") {
      return ["planner", "implement", "test", "fix"];
    }
    return ALL_STEPS;
  }, [runType]);

  const readiness = useMemo(() => {
    const readyMap: Record<StepKey, boolean> = {
      router: steps?.router === "done",
      planner: steps?.planner === "done",
      implement: steps?.implement === "done",
      test: steps?.test === "done",
      fix: steps?.fix === "done",
    };

    const runningIndex = stepOrder.findIndex((step) => steps?.[step] === "running");

    let active: StepKey;

    if (runningIndex !== -1) {
      active = stepOrder[runningIndex];
    } else {
      const firstNotDoneIndex = stepOrder.findIndex(
        (step) => steps?.[step] !== "done"
      );

      if (firstNotDoneIndex !== -1) {
        active = stepOrder[firstNotDoneIndex];
      } else {
        active = stepOrder[stepOrder.length - 1];
      }
    }

    return { readyMap, active };
  }, [steps, stepOrder]);

  return (
    <div className="min-h-screen w-full bg-neutral-900 text-neutral-100">
      <div className="mx-auto max-w-6xl px-4 py-6 space-y-6 pt-6">
        <nav className="flex items-center justify-center gap-3 pt-20">
          {stepOrder.map((key, i) => {
            const isReady = readiness.readyMap[key];
            const isActive = readiness.active === key && !isReady;
            return (
              <div key={key} className="flex items-center justify-center gap-3">
                <StepPill
                  label={labelFor(key)}
                  icon={iconFor(key)}
                  active={isActive}
                  done={isReady}
                />
                {i < stepOrder.length - 1 && (
                  <span className="text-neutral-500 select-none">—</span>
                )}
              </div>
            );
          })}
        </nav>

        <div className="h-[calc(100vh-16rem)] overflow-y-auto">
          <Chat messages={logs ?? []} isPending={true} />
        </div>
      </div>
    </div>
  );
}

function StepPill({
  label,
  icon,
  active,
  done,
}: {
  label: string;
  icon: JSX.Element;
  active?: boolean;
  done?: boolean;
}) {
  const base =
    "inline-flex items-center gap-2 rounded-full px-3 py-1 transition";
  const state = active
    ? "ring-2 ring-green-500/80 bg-green-900/20 text-green-300 scale-105 shadow-[0_0_0.5rem_rgba(34,197,94,0.35)]"
    : done
    ? "bg-neutral-800/60 text-neutral-200"
    : "bg-neutral-800/40 text-neutral-400";

  return (
    <span className={`${base} ${state}`}>
      <span
        className={`grid place-items-center rounded-full ${
          active ? "h-7 w-7" : "h-6 w-6"
        }`}
      >
        {icon}
      </span>
      <span className={`text-sm ${active ? "font-semibold" : ""}`}>
        {label}
      </span>
    </span>
  );
}

function labelFor(step: StepKey) {
  switch (step) {
    case "router":
      return "Route";
    case "planner":
      return "Plan";
    case "implement":
      return "Build";
    case "test":
      return "Test";
    case "fix":
      return "Fix";
  }
}

function iconFor(step: StepKey) {
  switch (step) {
    case "router":
      return (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" />
          <path d="M14.5 9.5l-4 2-2 4 4-2 2-4z" />
        </svg>
      );
    case "planner":
      return (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12a8 8 0 1 1-3.6-6.7L21 5v7z" />
        </svg>
      );
    case "implement":
      return (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2l8 4-8 4-8-4 8-4z" />
          <path d="M4 6v8l8 4 8-4V6" />
        </svg>
      );
    case "test":
      return (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 3h6M10 3v6l-5 8h14l-5-8V3" />
        </svg>
      );
    case "fix":
      return (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      );
  }
}
