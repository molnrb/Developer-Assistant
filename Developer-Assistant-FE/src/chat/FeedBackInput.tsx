import { PaperAirplaneIcon, PlusIcon } from "@heroicons/react/24/solid";
import useChatInput from "../hooks/use-chat-input";
import { useRunStore } from "../state/runStore";
import useProjectStore from "../state/ProjectStore";
import useAuthStore from "../state/useAuthStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


export function ModifyProject() {
  const { prompt, handleKeyDown, handleChange } = useChatInput("", () => handleStart(prompt));
  const { getProject } = useProjectStore();
  const project = getProject();
  const token = useAuthStore((s) => s.token);
  const { setRunning, reset, setRunId, appendLog, initRun } = useRunStore();

  async function handleStart(prompt: string) {
    const id = project?.id;
    if (!prompt.trim() || !id) return;
    initRun(id, "modify");

    await fetch(`${API_BASE_URL}/runs/${id}/modify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" ,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ prompt: prompt }),
    });
    reset();
    setRunId(id);
    setRunning(true);
    appendLog(prompt, true);
  }

  return (
    <div className="w-full flex justify-center items-center p-4 dark:bg-zinc-900">
      <div className="flex items-center w-full max-w-3xl rounded-full bg-zinc-800 px-4 py-2 shadow-sm border border-zinc-700">
        <PlusIcon className="h-5 w-5 text-zinc-400 mr-3" />

        <textarea
          value={prompt}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Modify your project..."
          className="w-full resize-none bg-transparent text-base text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-0 scrollbar-none"
        ></textarea>

        {prompt.length > 0  && (
          <button
            onClick={() => handleStart(prompt)}
            className="ml-2 p-2 rounded-full hover:bg-zinc-700 transition"
          >
            <PaperAirplaneIcon className="h-5 w-5 text-zinc-200 -rotate-45" />
          </button>
        )}
      </div>
    </div>
  );
}
