import type { Message } from "../state/ProjectStore";
import { ChatMessage } from "./ChatMessage";
import { ChatPendingLoader } from "../ui/Loaders";
import { useScrollToElement } from "../hooks/use-scroll-to-element";

type ChatProps = { messages: Message[]; isPending?: boolean };

export function Chat({ messages, isPending = false }: ChatProps) {
  const endRef = useScrollToElement<HTMLDivElement>(messages);

  return (
    <div className="flex h-full overflow-auto">
      <div className="mx-auto w-full max-w-3xl px-4 sm:px-6 lg:px-8 py-6">
        {messages.length > 0 ? (
          messages.map((m) => (
            <ChatMessage key={m.id} fromUser={m.fromUser} content={m.content} />
          ))
        ) : (
          <div className="flex h-full items-center justify-center py-24">
            <h1 className="text-center text-xl text-zinc-500 dark:text-zinc-400">Welcome</h1>
          </div>
        )}
        {isPending && <div className="mt-4 justify-center"><ChatPendingLoader /></div>}
        <div ref={endRef} className="h-0" />
      </div>
    </div>
  );
}
