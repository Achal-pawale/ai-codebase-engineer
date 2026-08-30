import { Sparkles, User } from "lucide-react";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { formatAnswerHtml } from "@/lib/formatAnswer";
import { truncateMiddle } from "@/lib/utils";

export interface AskMessage {
  id: string;
  question: string;
  status: "loading" | "done" | "error";
  answer?: string;
  sources?: string[];
  model?: string;
  error?: unknown;
}

export function ChatMessage({ message }: { message: AskMessage }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-base-700 text-ink-400">
          <User size={13} />
        </div>
        <p className="mt-0.5 text-sm text-ink-100">{message.question}</p>
      </div>

      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent-bright">
          <Sparkles size={13} />
        </div>
        <div className="min-w-0 flex-1">
          {message.status === "loading" && <LoadingState message="Generating answer…" compact />}

          {message.status === "error" && <ErrorState error={message.error} compact />}

          {message.status === "done" && message.answer && (
            <>
              <div
                className="whitespace-pre-wrap text-sm leading-relaxed text-ink-200"
                dangerouslySetInnerHTML={{ __html: formatAnswerHtml(message.answer) }}
              />
              {message.sources && message.sources.length > 0 && (
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-ink-600">Sources:</span>
                  {message.sources.map((src) => (
                    <span key={src} className="rounded bg-base-700 px-1.5 py-0.5 font-mono text-[11px] text-ink-400" title={src}>
                      {truncateMiddle(src, 28)}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
