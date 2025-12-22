import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

export interface ProjectFile {
  name: string;
  content: string;
}

export interface Message {
  id: number;
  content: string;
  fromUser: boolean;
}

export interface Project {
  id: string;
  title: string;
  files: ProjectFile[];
  activeFile?: string | null;
  messages: Message[];
  isPending: boolean;
}

const genId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const createEmptyProject = (title = "Undefined Project"): Project => ({
  id: genId(),
  title,
  files: [],
  activeFile: null,
  messages: [],
  isPending: false,
});

interface ProjectStore {
  project: Project | null;
  ready: boolean;

  getProject: () => Project | null;
  getFiles: () => ProjectFile[];
  getMessages: () => Message[];

  setProject: (project: Project) => void;

  setId: (id: string) => void;
  setMessages: (messages: Message[]) => void;
  setReady: (ready: boolean) => void;

  resetProject: (title?: string) => void;

  renameProject: (newTitle: string) => void;
  setIsPending: (value: boolean) => void;
  deleteFile: (fileName: string) => void;
  setActiveFile: (fileName: string | null) => void;
  setFiles: (files: ProjectFile[]) => void;
  updateFile: (fileName: string, newContent: string) => void;
  addFile: (file: ProjectFile) => void;

  addMessage: (content: string, fromUser: boolean) => void;
}

const useProjectStore = create<
  ProjectStore,
  [["zustand/devtools", never], ["zustand/persist", ProjectStore]]
>(
  devtools(
    persist(
      (set, get) => ({
        project: createEmptyProject(),
        ready: false,

        getProject: () => get().project,
        getFiles: () => get().project?.files ?? [],
        getMessages: () => get().project?.messages ?? [],

        setProject: (project) =>
          set(() => ({ project })),

        setReady: (ready) => set(() => ({ ready })),

        resetProject: (title) =>
          set(() => {
            const fresh = createEmptyProject(title);
            return {
              project: fresh,
              ready: false,
            };
          }),

        renameProject: (newTitle) =>
          set((state) =>
            state.project
              ? { project: { ...state.project, title: newTitle } }
              : state
          ),

        addFile: (file) =>
          set((state) => {
            const p = state.project;
            if (!p) return state;
            const nextFiles = [...(p.files ?? []), file];
            return { project: { ...p, files: nextFiles } };
          }
        ),

        deleteFile: (fileName) =>
          set((state) => {
            const p = state.project;
            if (!p) return state;
            const nextFiles = p.files.filter((f) => f.name !== fileName);
            const nextActive =
              p.activeFile === fileName
                ? nextFiles[0]?.name ?? null
                : p.activeFile;
            return {
              project: { ...p, files: nextFiles, activeFile: nextActive },
            };
          }
        ),

        setIsPending: (value) =>
          set((state) =>
            state.project
              ? { project: { ...state.project, isPending: value } }
              : state
          ),
        
        setMessages: (messages) =>
          set((state) =>
            state.project ? { project: { ...state.project, messages: messages } } : state
          ),

        setId: (id) =>
          set((state) =>
            state.project ? { project: { ...state.project, id: id } } : state
          ),

        setActiveFile: (fileName) =>
          set((state) =>
            state.project
              ? {
                  project: { ...state.project, activeFile: fileName },
                }
              : state
          ),

        setFiles: (files) =>
          set((state) => {
            if (!state.project) return state;
            const nextActive =
              files.find((f) => f.name === state.project?.activeFile)?.name ??
              files[0]?.name ??
              null;
            return {
              project: { ...state.project, files, activeFile: nextActive },
            };
          }),

        updateFile: (fileName, newContent) =>
          set((state) => {
            const p = state.project;
            if (!p) return state;
            const files = p.files.map((f) =>
              f.name === fileName ? { ...f, content: newContent } : f
            );
            return { project: { ...p, files } };
          }),

        addMessage: (content, fromUser) =>
          set((state) => {
            console.log("Adding message:", { content, fromUser });
            console.log("Last message", state.project?.messages[state.project.messages.length - 1]);
            const p = state.project;
            if (!p) return state;
            const newId =
              (p.messages.length ? p.messages[p.messages.length - 1].id : 0) +
              1;
            return {
              project: {
                ...p,
                messages: [...p.messages, { id: newId, content, fromUser }],
              },
            };
          }),
      }),
      { name: "project-store-v1",
        partialize: (state) => {
          const p = state.project;
          if (!p) return state;
          const filtered = (p.files ?? []).filter(f => f.name !== "styles/tw-built.css");
          return {
            ...state,
            project: { ...p, files: filtered }
          };
        }
      }
    )
  )
);

export default useProjectStore;
