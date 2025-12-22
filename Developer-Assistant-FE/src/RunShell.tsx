import {   useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import useProjectStore from "./state/ProjectStore";
import { Chat } from "./chat/Chat";
import { ModifyProject } from "./chat/FeedBackInput";
import CodeSandbox from "./CodeSandbox";
import { Message } from "./state/ProjectStore";

type Pane = "preview" | "chat" | "code";

export function RunShell() {

  const project = useProjectStore((s) => s.getProject());
  const [main, setMain] = useState<Pane>("preview");

  return (
    <div className="relative h-full w-full bg-neutral-900 text-neutral-100 p-4 overflow-hidden">
      <AnimatePresence mode="wait">
        <motion.div
          key="result"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { duration: 0.25 } }}
          exit={{ opacity: 0, transition: { duration: 0.2 } }}
          className="absolute inset-0"
        >
          <MainLayout main={main} setMain={setMain} project={project} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}


type MainLayoutProps = {
  main: Pane;
  setMain: (pane: Pane) => void;
  project: { messages?: Message[] } | null;
};

function MainLayout({  main, setMain, project }: MainLayoutProps) {
  return (
    <motion.div className="h-full w-full" layout transition={{ type: "spring", stiffness: 280, damping: 28 }}>
      <div className="grid h-full w-full grid-cols-12 gap-4">
        <motion.div
          key={`large-${main}`}
          layout
          layoutId={`pane-${main}`}
          className="col-span-12 lg:col-span-8 h-full rounded-2xl border border-neutral-800 bg-neutral-950/60 shadow-xl overflow-hidden"
        >
          <Pane kind={main} messages={project?.messages ?? []} large />
        </motion.div>

        <div className="col-span-12 lg:col-span-4 h-full flex flex-col gap-4 min-h-0">
          {(["preview", "chat", "code"] as Pane[])
            .filter((p) => p !== main)
            .map((p) => (
              <motion.div
                key={`small-${p}`}
                layout
                layoutId={`pane-${p}`}
                className="flex-1 min-h-0 rounded-2xl border border-neutral-800 bg-neutral-950/40 overflow-hidden relative"
                transition={{ type: "spring", stiffness: 280, damping: 28 }}
              >
                <button
                  onClick={() => setMain(p)}
                  className="absolute top-2 right-2 z-10 rounded-full bg-white/10 hover:bg-white/20 text-neutral-200 p-2 backdrop-blur transition"
                  title="Expand"
                >
                  <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M7 17h10V7" />
                    <path d="M17 17L7 7" />
                  </svg>
                </button>
                <Pane kind={p}  messages={project?.messages ?? []} />
              </motion.div>
            ))}
        </div>
      </div>
    </motion.div>
  );
}

function Pane({
  kind,
  messages,
}: {
  kind: Pane;
  large?: boolean;
  messages: Message[];
}) {
  if (kind === "preview") {
    return (
      <div className="h-full w-full flex flex-col min-h-0">
        <Bar title="Preview" />
        <div className="flex-1 min-h-0">
          <CodeSandbox view="preview" />
        </div>
      </div>
    );
  }
  if (kind === "code") {
    return (
      <div className="h-full w-full flex flex-col min-h-0">
        <Bar title="Code" />
        <div className="flex-1 min-h-0">
          <CodeSandbox view="editor" />
        </div>
      </div>
    );
  }
  return (
    <div className="h-full w-full flex flex-col min-h-0">
      <Bar title="Chat" />
      <div className="flex-1 min-h-0 flex flex-col">
        <Chat messages={messages} />
        <ModifyProject />
      </div>
    </div>
  );
}

function Bar({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-800 bg-neutral-900/60">
      <span className="text-sm text-neutral-300">{title}</span>
    </div>
  );
}
