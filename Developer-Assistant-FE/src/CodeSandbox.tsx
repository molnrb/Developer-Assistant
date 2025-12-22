import CodeEditor from "./CodeEditor";
import { SandpackProvider } from "@codesandbox/sandpack-react";
import useProjectStore from "./state/ProjectStore";
import { ProjectPreview } from "./ProjectPreview";
import CodePreview from "./CodePreview";
import useUIStateStore from "./state/UIStateStore";


export default function ReactSandboxEnvironment({ view }: { view: "editor" | "preview" }) {
  const { getProject } = useProjectStore();
  const { isSandboxMode } = useUIStateStore();

  const files: Record<string, { code: string; hidden?: boolean }> = Object.fromEntries(
    (getProject()?.files || []).map((file) => [ `/${file.name}`, { code: file.content } ])
  );



  if (!files["/tsconfig.json"]) {
    files["/tsconfig.json"] = {
      code: JSON.stringify({
        compilerOptions: {
          target: "ESNext",
          module: "ESNext",
          jsx: "react-jsx",
          moduleResolution: "Node",
          esModuleInterop: true,
          strict: true,
          skipLibCheck: true,
        },
        include: ["./*"],
      }, null, 2),
    };
  }

  if (!files["/package.json"]) {
    files["/package.json"] = {
      code: JSON.stringify({
        name: "sandbox-react",
        version: "1.0.0",
        main: "index.tsx",
        dependencies: {
          react: "latest",
          "react-dom": "latest",
        },
      }, null, 2),
    };
  }

  return (
    <div className="flex-1 w-full h-full overflow-hidden">
      <SandpackProvider
        options={{
          autoReload: true,
          autorun: true,
          recompileMode: "immediate",
        }}
        key={getProject()?.id || "new-project"}
        files={files}
        customSetup={{
          entry: "/src/main.tsx",
          dependencies: {
            react: "latest",
            "react-dom": "latest",
            "react-router-dom": "latest",
          },
        }}
      >
        {view === "editor" ? <CodeEditor /> : isSandboxMode ? <CodePreview /> : <ProjectPreview runId={getProject()?.id || ""} />}
      </SandpackProvider>
    </div>
  );
}
