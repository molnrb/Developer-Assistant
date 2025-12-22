import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import "highlight.js/styles/github-dark.css";
import { ComponentPropsWithoutRef } from "react";

type ChatAIResponseMessageProps = {
  content: string;
};

export default function ChatAIResponseMessage({
  content,
}: ChatAIResponseMessageProps) {
  return (
    <div className="flex items-start space-x-2">
      <div className="markdown-content flex-1 p-2">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={{
            p: ({ children }) => (
              <p className="text-base font-semibold font-sans tracking-tight text-gray-900 dark:text-gray-100 mb-2">
                {children}
              </p>
            ),
            strong: ({ children }) => (
              <strong className="font-bold text-gray-900 dark:text-gray-100">
                {children}
              </strong>
            ),
            code: ({
              inline,
              className,
              children,
              ...props
            }: ComponentPropsWithoutRef<"code"> & { inline?: boolean }) => {
              if (inline) {
                return (
                  <code
                    className="bg-gray-200 dark:bg-gray-700 px-2 py-1 rounded-md text-base font-semibold font-sans tracking-tight"
                    {...props}
                  >
                    {children}
                  </code>
                );
              }
              return (
                <div className="rounded-lg overflow-hidden border border-gray-900 bg-gray-900 shadow-lg">
                  <pre className="overflow-x-auto text-sm font-mono text-gray-100 p-4">
                    <code {...props} className={`${className ?? ""}`}>
                      {children}
                    </code>
                  </pre>
                </div>
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
