import { useEffect, useMemo, useRef, useState } from "react";
import { useProjects } from "../hooks/useProjects";
import useLoadProject from "../hooks/useGetProject";
import { useDownloadArtifact } from "../hooks/useDownloadArtifact";
import { useRunTelemetry } from "../hooks/useRunTelemetry";
import useProjectStore from "../state/ProjectStore";
import { useUpdateTitle } from '../hooks/useUpdateTitle';
import useAuthStore from "../state/useAuthStore";
import { useAppView } from "../hooks/useAppView";
import { useKillRun } from "../hooks/useKillRun";
import { useDeleteProject } from "../hooks/useProjectHooks";
import useUIStateStore from "../state/UIStateStore";

type Project = { id: string; title: string; updatedAt?: string };

interface HeaderProps {
  onNewProject?: () => void;
  runId?: string | null;
}

export default function Header({
  onNewProject,
  runId
}: HeaderProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const  view  = useAppView();
  const { killRun, isPending: isKilling } = useKillRun();
  const { logout } = useAuthStore();
  const projectStore = useProjectStore();
  const [open, setOpen] = useState(false);         
  const [menuOpen, setMenuOpen] = useState(false); 
  const [renaming, setRenaming] = useState(false); 
  const [query, setQuery] = useState("");
  const [newTitle, setNewTitle] = useState(projectStore.project?.title ?? "");
  const deleteProject = useDeleteProject();

  const { isSandboxMode, setIsSandboxMode } = useUIStateStore();

  const { projects, isLoading, isError, error } = useProjects(open);
  const { getProject: loadProject, isPending } = useLoadProject();


  const { mutate: updateTitle } = useUpdateTitle();
  const { downloadAndSave, isPending: isDownloading } = useDownloadArtifact();
  const { data: telemetry } = useRunTelemetry(runId ?? null, {
    enabled: menuOpen && !!runId,
    refetchMs: 1500,
  });

  const panelRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (open && panelRef.current && !panelRef.current.contains(t) && !btnRef.current?.contains(t)) setOpen(false);
      if (menuOpen && menuRef.current && !menuRef.current.contains(t) && !menuBtnRef.current?.contains(t)) setMenuOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (open) setOpen(false);
        if (menuOpen) setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open, menuOpen]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = projects.map(p => ({ id: (p as Project).id, title: (p as Project).title, updatedAt: (p as Project).updatedAt }));
    return q ? base.filter(p => p.title.toLowerCase().includes(q)) : base;
  }, [projects, query]);

  const handleDangerousAction = () => {
    localStorage.removeItem("token");
    logout();
  };

  return (
    <header className="sticky top-0 z-40 h-14 w-full bg-[#0f1115]/85 backdrop-blur border-b border-[#232637] text-white">
      <div className="relative h-full">
        <div className="absolute inset-y-0 left-0 flex items-center gap-2 pl-4">
          <div className="relative">
            <button
              ref={menuBtnRef}
              onClick={() => setMenuOpen(v => !v)}
              aria-label="Menu"
              className="p-2 rounded-md hover:bg-[#171923] active:scale-[0.98] transition"
            >
              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
            </button>

            {menuOpen && (
              <div
                ref={menuRef}
                className="absolute left-0 mt-2 w-64 rounded-xl overflow-hidden border border-[#232637] bg-[#0e1117] shadow-xl"
                role="menu"
              >
                
                <button
                  onClick={() => {
                    if (!onNewProject) return;
                    onNewProject();
                    setMenuOpen(false);
                  }}
                  disabled={!onNewProject}
                  className={`w-full text-left px-3 py-2.5 text-sm hover:bg-[#151924] border-t border-[#232637] ${!onNewProject ? "opacity-50 cursor-not-allowed" : ""}`}
                  role="menuitem"
                >
                  New project
                </button>

                <button
                  onClick={() => {
                    setIsSandboxMode(!isSandboxMode);
                    setMenuOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2.5 text-sm hover:bg-[#151924] border-[#232637] ${!onNewProject ? "opacity-50 cursor-not-allowed" : ""}`}
                  role="menuitem"
                >
                  Change preview to {isSandboxMode ? "iFrame" : "Sandbox"}
                </button>

                <button
                  onClick={async () => {
                    const project = projectStore.getProject();
                    if (project) {
                      await downloadAndSave(project.id);
                      setMenuOpen(false);
                    }
                  }}
                  disabled={ view!="shell" || isDownloading}
                  className={`w-full text-left px-3 py-2.5 text-sm hover:bg-[#151924] ${( view!="shell" || isDownloading) ? "opacity-50 cursor-not-allowed" : ""}`}
                  role="menuitem"
                >
                  {isDownloading ? "Downloading…" : "Download artifact (.zip)"}
                </button>

                <div className="px-3 py-2.5 text-sm border-t border-[#232637]">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-300">Telemetry</span>
                    <span className={`text-xs px-2 py-0.5 rounded bg-[#141824] border border-[#232637] ${telemetry?.status === "passed" ? "text-green-300" : "text-yellow-300"}`}>
                      {telemetry?.status ?? (runId ? "…" : "n/a")}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-400">
                    <div>Steps: <span className="text-gray-200">{telemetry?.steps?.length ?? (runId ? "…" : "-")}</span></div>
                    <div>Files Ready: <span className="text-gray-200">{telemetry?.filesCount ?? (runId ? "…" : "-")}</span></div>
                    <div>Planned Files: <span className="text-gray-200">{telemetry?.planCount ?? (runId ? "…" : "-")}</span></div>
                    <div>Tests: <span className="text-gray-200">{telemetry?.metrics?.test ? JSON.stringify(telemetry.metrics.test) : (runId ? "…" : "-")}</span></div>
                    <div>Tokens: <span className="text-gray-200">{typeof telemetry?.tokens === 'object' ? JSON.stringify(telemetry.tokens) : telemetry?.tokens ?? (runId ? "…" : "-")}</span></div>
                    <div>Metrics: <span className="text-gray-200">{typeof telemetry?.metrics === 'object' ? JSON.stringify(telemetry.metrics) : telemetry?.metrics ?? (runId ? "…" : "-")}</span></div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="relative">
            {!renaming ? (
              <div
                className="h-9 px-3 inline-flex items-center gap-2 rounded-md border border-[#232637] bg-[#171923] hover:bg-[#1b1f2a] text-sm font-medium transition cursor-pointer select-none"
              >
                <span
                  className="truncate max-w-[220px]"
                  onClick={() => {
                    if(view==="shell") {
                      setNewTitle(projectStore.project?.title ?? "");
                      setRenaming(true);
                      setMenuOpen(false);
                    }
                  }}
                >
                  {projectStore.project?.title ?? "Select project"}
                </span>

                <svg
                  onClick={(e) => {
                    if(view!="run") {
                      e.stopPropagation();
                      setOpen((v) => !v);
                    }
                  }}
                  className={`w-4 h-4 transition-transform cursor-pointer ${open ? "rotate-180" : ""}`}
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path d="M5.23 7.21a.75.75 0 011.06.02L10 11.17l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" />
                </svg>
              </div>
            ) : (
              <input
                autoFocus
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onBlur={() => {
                  if (newTitle.trim() && newTitle !== projectStore.project?.title) {
                    projectStore.renameProject(newTitle);
                    updateTitle(newTitle);
                  }
                  setRenaming(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    if (newTitle.trim() && newTitle !== projectStore.project?.title) {
                      projectStore.renameProject(newTitle);
                      updateTitle(newTitle);
                    }
                    setRenaming(false);
                  } else if (e.key === "Escape") {
                    setRenaming(false);
                  }
                }}
                className="h-9 px-3 rounded-md border border-[#232637] bg-[#171923] text-sm w-full"
              />
            )}

            {open && (
              <div
                ref={panelRef}
                className="absolute left-0 mt-2 w-[320px] rounded-xl overflow-hidden border border-[#232637] bg-[#0e1117] shadow-xl"
                role="listbox"
              >
                <div className="p-2 border-b border-[#232637]">
                  <div className="flex items-center gap-2 px-2 h-9 rounded-md bg-[#141824]">
                    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="11" cy="11" r="7" />
                      <path d="M21 21l-4.3-4.3" />
                    </svg>
                    <input
                      autoFocus
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search projects…"
                      className="w-full bg-transparent outline-none text-sm placeholder:text-gray-400"
                    />
                  </div>
                </div>

                <div className="max-h-72 overflow-auto">
                  {isLoading && (
                    <div className="px-3 py-3 text-sm text-gray-400">Loading…</div>
                  )}
                  {isError && (
                    <div className="px-3 py-3 text-sm text-red-400">
                      {(error as Error)?.message ?? 'Failed to load projects'}
                    </div>
                  )}
                  {!isLoading && !isError && filtered.length === 0 && (
                    <div className="px-3 py-3 text-sm text-gray-400">No projects found.</div>
                  )}

                  {!isLoading &&
                    !isError &&
                    filtered.map((p) => {
                      const selected = p.id === projectStore.project?.id;
                      const isDeleting =
                        deleteProject.isPending && deleteProject.variables === p.id;

                      return (
                        <div
                          key={p.id}
                          onClick={() => {
                            if (isPending || isDeleting) return;
                            loadProject(p.id);
                            setOpen(false);
                          }}
                          className={`w-full text-left px-3 py-2.5 text-sm hover:bg-[#151924] cursor-pointer ${
                            selected ? 'bg-[#141824]' : ''
                          } ${isPending || isDeleting ? 'opacity-70 cursor-wait' : ''}`}
                          role="option"
                          aria-selected={selected}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <span className="truncate">{p.title}</span>
                                {selected && (
                                  <svg
                                    viewBox="0 0 24 24"
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                  >
                                    <path d="M20 6L9 17l-5-5" />
                                  </svg>
                                )}
                              </div>
                              {p.updatedAt && (
                                <div className="text-[11px] text-gray-400 mt-0.5">
                                  Updated {new Date(p.updatedAt).toLocaleDateString()}
                                </div>
                              )}
                            </div>

                            <button
                              type="button"
                              className="ml-2 text-xs text-gray-500 hover:text-red-400 shrink-0"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (
                                  window.confirm(
                                    `Are you sure you want to delete project "${p.title}"?`
                                  )
                                ) {
                                  deleteProject.mutate(p.id);
                                }
                              }}
                              disabled={isDeleting}
                              aria-label={`Delete project ${p.title}`}
                            >
                              {isDeleting ? (
                                <span className="text-xs">…</span>
                              ) : (
                                <svg
                                  viewBox="0 0 24 24"
                                  className="w-4 h-4"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="2"
                                >
                                  <path d="M3 6h18" />
                                  <path d="M10 11v6" />
                                  <path d="M14 11v6" />
                                  <path d="M5 6l1 14h12l1-14" />
                                  <path d="M9 6V4h6v2" />
                                </svg>
                              )}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
          { view==="run" && (
            <button
              disabled={isKilling}
              onClick={() => killRun(runId || "")}
              className="px-3 py-1.5 rounded bg-red-900 text-sm text-white"
            >
              {isKilling ? "Stopping…" : "Cancel run"}
            </button>
          )}
        </div>

        <div className="absolute inset-y-0 right-0 flex items-center pr-4">
          <div className="flex items-center gap-3">
            

            {!confirmOpen ? (
              <><span className="text-sm text-gray-300 whitespace-nowrap">
                MoBa Assistant
              </span><button
                onClick={() => {
                  setConfirmOpen(true);
                } }
                aria-label="Open profile"
                className="w-8 h-8 rounded-full border border-[#2a2f43] bg-[#171923] grid place-items-center hover:bg-[#1b1f2a] transition"
              >
                  <svg
                    className="w-4 h-4"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <circle cx="12" cy="8" r="4" />
                    <path d="M6 20c2-3 10-3 12 0" />
                  </svg>
                </button></>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-300">
                  Do you want to log out?
                </span>
                <button
                  onClick={() => {
                    handleDangerousAction();
                    setConfirmOpen(false);
                  }}
                  className="px-3 py-1.5 text-xs rounded-md bg-red-600 hover:bg-red-500 text-white"
                >
                  Yes
                </button>
                <button
                  onClick={() => setConfirmOpen(false)}
                  className="px-3 py-1.5 text-xs rounded-md border border-[#232637] text-gray-200 hover:bg-[#151924]"
                >
                  No
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}