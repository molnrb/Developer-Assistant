import { useEffect, useRef, useState } from "react";
import useProjectStore from "./state/ProjectStore";
import { useRunStore } from "./state/runStore";
import useAuthStore from "./state/useAuthStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Domain = "auto" | "games" | "webshop" | "website" | "general";
type ModelId = "auto" | "gpt-5.1" | "gpt-5-mini";

const MODEL_OPTIONS: { value: ModelId; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "gpt-5.1", label: "GPT-5.1" },
  { value: "gpt-5-mini", label: "GPT-5 mini" },
];

export function NewRun({ onReady }: { onReady: (runId: string) => void }) {
  const token = useAuthStore((s) => s.token);
  const [desc, setDesc] = useState("");
  const { setRunning, reset, setRunId, appendLog, setRunType  } = useRunStore();
  const { resetProject, setId } = useProjectStore();

  const [domain, setDomain] = useState<Domain>("auto");
  const [planningModel, setPlanningModel] = useState<ModelId>("gpt-5.1");
  const [implementerModel, setImplementerModel] = useState<ModelId>("gpt-5-mini");
  const [fixerModel, setFixerModel] = useState<ModelId>("gpt-5-mini");

  const [openDomain, setOpenDomain] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target as Node)) setOpenDomain(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  async function handleStart() {
    if (!desc.trim()) return;

    const res = await fetch(`${API_BASE_URL}/runs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    });
    const { run_id } = await res.json();
    onReady(run_id);

    await fetch(`${API_BASE_URL}/runs/${run_id}/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        description: desc,
        domainOverride: domain,
        planningModel,
        implementerModel,
        fixerModel,
      }),
    });

    resetProject();
    reset();
    appendLog(desc, true);
    setId(run_id);
    setRunId(run_id);
    setRunning(true);
    setRunType("generate");
  }

  return (
    <div className="min-h-screen w-full bg-neutral-900 text-neutral-100 flex items-center justify-center">
      <div className="w-full max-w-4xl px-6">
        <h1 className="text-center text-3xl sm:text-5xl font-semibold mb-10 text-neutral-200">
          What are we building today?
        </h1>

        <div className="relative">
          <div className="mx-auto flex items-center gap-3 rounded-full bg-neutral-800/70 backdrop-blur px-4 sm:px-6 py-3 sm:py-4 shadow-lg ring-1 ring-black/20">
            <button
              type="button"
              onClick={() => setOpenDomain((o) => !o)}
              className="shrink-0 inline-flex items-center justify-center h-9 w-9 rounded-full bg-neutral-700 hover:bg-neutral-600"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" d="M4 8h10M4 16h16" />
                <circle cx="16" cy="8" r="2" />
                <circle cx="10" cy="16" r="2" />
              </svg>
            </button>

            <input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleStart()}
              placeholder="Ask anything…"
              className="flex-1 bg-transparent placeholder-neutral-400 focus:outline-none text-base sm:text-lg"
            />
          </div>

          {openDomain && (
            <div
              ref={menuRef}
              className="absolute left-0 top-14 sm:top-16 z-20 w-[900px] rounded-xl bg-neutral-800 text-neutral-200 shadow-2xl ring-1 ring-black/30 p-4"
            >
              <div className="grid grid-cols-4 gap-6">
                <div>
                  <div className="mb-2 text-xs uppercase opacity-60">Domain</div>
                  <div className="flex flex-col gap-1">
                    {(["auto", "games", "webshop", "website", "general"] as Domain[]).map((d) => (
                      <button
                        key={d}
                        onClick={() => setDomain(d)}
                        className={`px-3 py-2 rounded text-sm text-left hover:bg-neutral-700 ${
                          domain === d ? "bg-neutral-700/60" : ""
                        }`}
                      >
                        {labelFor(d)}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs uppercase opacity-60">Planning model</div>
                  <div className="flex flex-col gap-1">
                    {MODEL_OPTIONS.map((m) => (
                      <button
                        key={m.value}
                        onClick={() => setPlanningModel(m.value)}
                        className={`px-3 py-2 rounded text-sm text-left hover:bg-neutral-700 ${
                          planningModel === m.value ? "bg-neutral-700/60" : ""
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs uppercase opacity-60">Implementer model</div>
                  <div className="flex flex-col gap-1">
                    {MODEL_OPTIONS.map((m) => (
                      <button
                        key={m.value}
                        onClick={() => setImplementerModel(m.value)}
                        className={`px-3 py-2 rounded text-sm text-left hover:bg-neutral-700 ${
                          implementerModel === m.value ? "bg-neutral-700/60" : ""
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs uppercase opacity-60">Fixer model</div>
                  <div className="flex flex-col gap-1">
                    {MODEL_OPTIONS.map((m) => (
                      <button
                        key={m.value}
                        onClick={() => setFixerModel(m.value)}
                        className={`px-3 py-2 rounded text-sm text-left hover:bg-neutral-700 ${
                          fixerModel === m.value ? "bg-neutral-700/60" : ""
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-sm text-neutral-400 space-y-1">
          <span>
            Press <kbd className="px-1 py-0.5 rounded bg-neutral-800 border border-neutral-700">Enter</kbd> • Domain:{" "}
            <span className="text-neutral-300">{labelFor(domain)}</span>
          </span>
          <br />
          <span className="text-xs sm:text-sm">
            Planning: {planningModel} • Implementer: {implementerModel} • Fixer: {fixerModel}
          </span>
        </p>
      </div>
    </div>
  );
}

function labelFor(d: Domain) {
  switch (d) {
    case "auto": return "Auto (router)";
    case "games": return "Games";
    case "webshop": return "Webshop";
    case "website": return "Website";
    case "general": return "General";
  }
}
