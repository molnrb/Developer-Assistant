import ChatAIResponseMessage from "./ChatAIResponseMessage";

type ChatMessageProps = {
  fromUser: boolean;
  content: string;
};

export function ChatMessage({ fromUser, content }: ChatMessageProps) {
  return (
    <div
      className={`flex mt-4 ${
        fromUser ? "justify-end md:ml-64" : "justify-start"
      } items-center gap-2`}
    >
      <div
        className={`rounded-3xl p-4 ${
          fromUser
            ? "bg-zinc-200 dark:bg-zinc-800"
            : "bg-transparent"
        }`}
      >
        {!fromUser ? (
          <ChatAIResponseMessage content={content} />
        ) : (
          <div className="whitespace-pre-line text-base font-semibold font-sans tracking-tight text-gray-900 dark:text-gray-100">
            {content}
          </div>
        )}
      </div>
    </div>
  );
}
