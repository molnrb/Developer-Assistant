import { useEffect } from "react";
import { SandpackPreview, useSandpack, SandpackLayout } from "@codesandbox/sandpack-react";
import useProjectStore from "./state/ProjectStore";

export default function CodePreview() {
  const { dispatch } = useSandpack();
  const { getProject } = useProjectStore();
  const projectFilesHash = JSON.stringify(
    getProject()?.files.map((f) => [f.name, f.content])
  );

  useEffect(() => {
    dispatch({ type: "refresh" });
  }, [dispatch, projectFilesHash]);

  return (
    <div className="flex flex-col w-full h-full">
      <div className="flex-1 overflow-hidden relative">
        <SandpackLayout style={{ height: "100%" }}>
          <SandpackPreview
            style={{ width: "100%", height: "100%" }}
            showOpenInCodeSandbox={false}
            showRestartButton={false}
          />
        </SandpackLayout> 
      </div>
    </div>
  );
}
