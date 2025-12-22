import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  EllipsisVerticalIcon,
  PlusIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  DocumentIcon,
  FolderIcon,
} from "@heroicons/react/24/outline";
import CodeMirror from "@uiw/react-codemirror";
import { EditorView } from "@codemirror/view";
import { javascript } from "@codemirror/lang-javascript";
import prettier from "prettier/standalone";
import parserBabel from "prettier/plugins/babel";
import parserTypescript from "prettier/plugins/typescript";
import parserHtml from "prettier/plugins/html";
import parserEstree from "prettier/plugins/estree";

import useProjectStore from "./state/ProjectStore";
import useAuthStore from "./state/useAuthStore";
import { useDebouncedFileSave } from "./hooks/useDebouncedFileSave";
import { useRenameFile } from "./hooks/useRenameFile";

import { useAddFile, useDeleteFile } from "./hooks/useProjectHooks";

type TreeNode =
  | { type: "folder"; name: string; path: string; children: TreeNode[] }
  | { type: "file"; name: string; path: string };

function buildTree(paths: string[]): TreeNode[] {
  interface DirNode {
    __dir: true;
    children: Record<string, DirNode | FileNode>;
    path: string;
  }
  interface FileNode {
    __file: true;
    path: string;
  }
  const root: Record<string, DirNode | FileNode> = {};
  for (const p of paths) {
    const parts = p.split("/").filter(Boolean);
    let cur = root;
    parts.forEach((part, idx) => {
      const isFile = idx === parts.length - 1;
      if (isFile) {
        cur[part] = cur[part] || { __file: true, path: parts.slice(0, idx + 1).join("/") };
      } else {
        cur[part] = cur[part] || { __dir: true, children: {}, path: parts.slice(0, idx + 1).join("/") };
        cur = (cur[part] as DirNode).children;
      }
    });
  }
  const toArray = (obj: Record<string, unknown>): TreeNode[] =>
    Object.keys(obj)
      .sort((a, b) => a.localeCompare(b))
      .map((key) => {
        const v = obj[key] as { __file?: boolean; __dir?: boolean; path: string; children?: Record<string, unknown> };
        if (v.__file) return { type: "file", name: key, path: v.path } as TreeNode;
        return { type: "folder", name: key, path: v.path, children: toArray(v.children ?? {}) } as TreeNode;
      });
  return toArray(root);
}

export default function CodeEditor() {
  const token = useAuthStore((s) => s.token ?? undefined);
  const project = useProjectStore((s) => s.getProject());
  const activeFile = useProjectStore((s) => s.project?.activeFile);
  const setActiveFile = useProjectStore((s) => s.setActiveFile);
  const setFiles = useProjectStore((s) => s.setFiles);
  const updateFile = useProjectStore((s) => s.updateFile);

  const fileContent = project?.files.find((f) => f.name === activeFile)?.content || "";
  const fileExtension = activeFile?.split(".").pop() || "js";
  const [localCode, setLocalCode] = useState(fileContent);

  const { save, flush, isSaving } = useDebouncedFileSave({
    projectId: project?.id ?? "",
    fileName: activeFile ?? "",
    delayMs: 1200,
    token,
  });

  const { renameFile, isRenaming } = useRenameFile({
    projectId: project?.id ?? "",
    token,
  });
  const {
    mutate: addFileMutate,
    isPending: isAdding,
    error: addError,
  } = useAddFile(project?.id ?? "");
  const {
    mutate: deleteFileMutate,
    isPending: isDeleting,
    error: deleteError,
  } = useDeleteFile(project?.id ?? "");

  const fitTheme = EditorView.theme({
    "&": { height: "100%" },
    ".cm-scroller": { overflow: "auto" },
    ".cm-content": { minHeight: "100%" },
  });

  const scrollPastEnd = EditorView.theme({
    ".cm-scroller": { overflow: "auto" },
    ".cm-content": { paddingBottom: "20vh" },
  });

  useEffect(() => setLocalCode(fileContent), [fileContent]);

  const fileNames = useMemo(() => project?.files.map((f) => f.name) ?? [], [project?.files]);
  const tree = useMemo(() => buildTree(fileNames), [fileNames]);

  const [openDirs, setOpenDirs] = useState<Set<string>>(new Set(["public"]));
  const toggleDir = useCallback((path: string) => {
    setOpenDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const handleSave = useCallback(async () => {
    if (!project || !activeFile) return;
    try {
      const formatted = await prettier.format(localCode, {
        parser: fileExtension === "ts" || fileExtension === "tsx" ? "typescript" : "babel",
        plugins: [parserBabel, parserTypescript, parserHtml, parserEstree],
      });
      setLocalCode(formatted);
      save(formatted);
      flush();
    } catch {
      save(localCode);
      flush();
    }
  }, [project, activeFile, localCode, fileExtension, save, flush]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      handleSave();
    }
  };

  const handleAddFile = () => {
    if (!project) return;
    const newName = prompt("New file path (e.g., src/components/NewFile.tsx):");
    if (!newName) return;
    if (project.files.some((f) => f.name === newName)) {
      alert("File already exists!");
      return;
    }
    const initialContent = "// New file";
    const nextFiles = [...project.files, { name: newName, content: initialContent }];
    setFiles(nextFiles);
    setActiveFile(newName);

    addFileMutate(
      { name: newName, content: initialContent },
      {
        onError: (err: { message: unknown }) => {
          alert(err instanceof Error ? err.message : "Failed to add file");
          setFiles(project.files);
          if (activeFile && activeFile !== newName) {
            setActiveFile(activeFile);
          } else {
            const fallback = project.files[0]?.name ?? null;
            setActiveFile(fallback);
          }
        },
      }
    );
  };

  const handleDeleteFile = (name: string) => {
    if (!project) return;
    if (!confirm(`Delete ${name}?`)) return;

    const prevFiles = project.files;
    const newFiles = prevFiles.filter((file) => file.name !== name);
    const prevActive = activeFile ?? null;

    setFiles(newFiles);
    if (name === activeFile) {
      const fallback = newFiles[0]?.name ?? null;
      setActiveFile(fallback);
    }

    deleteFileMutate(
      { name },
      {
        onError: (err: { message: unknown }) => {
          alert(err instanceof Error ? err.message : "Failed to delete file");
          setFiles(prevFiles);
          setActiveFile(prevActive);
        },
      }
    );
  };

  const handleRenameFile = (oldName: string) => {
    if (!project) return;
    const oldBase = oldName.split("/").pop() ?? oldName;
    const newBase = prompt("New file name:", oldBase);
    if (!newBase || newBase.trim() === "" || newBase === oldBase) return;

    const dir = oldName.includes("/") ? oldName.slice(0, oldName.lastIndexOf("/") + 1) : "";
    const newName = dir + newBase.trim();

    if (project.files.some((f) => f.name === newName)) {
      alert("File already exists!");
      return;
    }

    renameFile({ oldName, newName });
  };

  function FileRow({ node }: { node: Extract<TreeNode, { type: "file" }> }) {
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
      const onClick = (e: MouseEvent) => {
        if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
      };
      window.addEventListener("click", onClick);
      return () => window.removeEventListener("click", onClick);
    }, []);

    const isActive = node.path === activeFile;

    return (
      <div
        className={`group flex items-center justify-between rounded-md px-2 py-1.5 cursor-pointer ${
          isActive ? "bg-white dark:bg-zinc-900 ring-1 ring-[#10a37f]/30" : "hover:bg-zinc-200/70 dark:hover:bg-zinc-700/60"
        }`}
      >
        <button
          className="flex items-center gap-2 flex-1 text-sm text-zinc-800 dark:text-zinc-100"
          onClick={() => setActiveFile(node.path)}
          title={node.path}
        >
          <DocumentIcon className="h-4 w-4 text-[#10a37f]" />
          <span className="truncate">{node.name}</span>
        </button>
        <div className="relative" ref={menuRef}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen((v) => !v);
            }}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-zinc-300/60 dark:hover:bg-zinc-600/60"
            aria-label="File menu"
          >
            <EllipsisVerticalIcon className="h-4 w-4 text-zinc-600 dark:text-zinc-300" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 mt-1 w-40 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 shadow-lg z-10">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpen(false);
                  handleRenameFile(node.path);
                }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded-t-lg disabled:opacity-60"
                disabled={isRenaming || isDeleting || isAdding}
              >
                Rename
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpen(false);
                  handleDeleteFile(node.path);
                }}
                className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-b-lg disabled:opacity-60"
                disabled={isDeleting || isRenaming || isAdding}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  function FolderRow({ node }: { node: Extract<TreeNode, { type: "folder" }> }) {
    const open = openDirs.has(node.path);
    return (
      <div>
        <button
          onClick={() => toggleDir(node.path)}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-zinc-800 dark:text-zinc-100 hover:bg-zinc-200/70 dark:hover:bg-zinc-700/60"
          title={node.path}
        >
          {open ? <ChevronDownIcon className="h-4 w-4 text-zinc-500" /> : <ChevronRightIcon className="h-4 w-4 text-zinc-500" />}
          <FolderIcon className="h-4 w-4 text-[#10a37f]" />
          <span className="truncate">{node.name}</span>
        </button>
        {open && (
          <div className="ml-4 mt-1 flex flex-col gap-1">
            {node.children.map((child) =>
              child.type === "folder" ? <FolderRow key={child.path} node={child} /> : <FileRow key={child.path} node={child} />
            )}
          </div>
        )}
      </div>
    );
  }

  const status =
    isRenaming ? "Renaming…" : isSaving ? "Saving…" : isAdding ? "Adding…" : isDeleting ? "Deleting…" : "";

  return (
    <div
      className="h-screen w-full grid grid-cols-[280px_1fr] grid-rows-[44px_1fr] bg-zinc-100 dark:bg-zinc-900"
      onKeyDown={handleKeyDown}
    >
      <header className="col-span-2 h-11 border-b border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/70 backdrop-blur flex items-center px-3">
        <div className="text-sm font-medium text-zinc-700 dark:text-zinc-200">{project?.title ?? "Project"}</div>
        <div className="ml-auto text-xs text-zinc-500 dark:text-zinc-400">{status}</div>
      </header>

      <aside className="border-r border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/40 p-2 flex flex-col min-h-0">
        <div className="flex items-center justify-between px-2 py-1">
          <span className="text-xs uppercase tracking-wide text-zinc-600 dark:text-zinc-400">Files</span>
          <button
            onClick={handleAddFile}
            disabled={isAdding || isRenaming || isDeleting}
            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-[#10a37f] text-white hover:opacity-90 disabled:opacity-60"
          >
            <PlusIcon className="h-3.5 w-3.5" />
            New
          </button>
        </div>
        <div className="mt-2 overflow-y-auto pr-1 flex-1 flex flex-col gap-1">
          {tree.length === 0 ? (
            <div className="text-xs text-zinc-500 px-2 py-2">No files yet</div>
          ) : (
            tree.map((n) => (n.type === "folder" ? <FolderRow key={n.path} node={n} /> : <FileRow key={n.path} node={n} />))
          )}
        </div>
        {(addError || deleteError) && (
          <div className="mt-2 text-xs text-red-600 px-2">
            {(addError || deleteError)?.message}
          </div>
        )}
      </aside>

      <main className="flex flex-col min-h-0">
        <div className="flex-1 min-h-0">
          <CodeMirror
            value={localCode}
            height="100%"
            extensions={[javascript({ typescript: true }), fitTheme, scrollPastEnd, EditorView.lineWrapping]}
            theme="dark"
            onChange={(val) => {
              setLocalCode(val);
              if (project && activeFile) {
                updateFile(activeFile, val);
                save(val);
              }
            }}
            basicSetup={{
              lineNumbers: true,
              foldGutter: true,
              highlightActiveLineGutter: true,
            }}
            style={{ fontSize: 14, height: "100%" }}
          />
        </div>
      </main>
    </div>
  );
}
