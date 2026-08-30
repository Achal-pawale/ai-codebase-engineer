import { useRef, useState } from "react";
import { MessageSquareText, Send } from "lucide-react";
import { useRepository } from "@/state/RepositoryContext";
import { askCodebase } from "@/api/chat";
import { retrieveChunks } from "@/api/repository";
import type { ScoredChunk } from "@/types/api";
import { ChatMessage, type AskMessage } from "@/components/ChatMessage";
import { EvidenceDock } from "@/components/code/EvidenceDock";
import { EmptyState } from "@/components/ui/EmptyState";

const EXAMPLE_PROMPTS = [
  "What does this repository do?",
  "How is the main entry point structured?",
  "Where is configuration loaded from?",
];

export function AskCodebasePage() {
  const { repoPath } = useRepository();
  const [messages, setMessages] = useState<AskMessage[]>([]);
  const [evidence, setEvidence] = useState<ScoredChunk[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const busy = messages.some((m) => m.status === "loading");

  const ask = async (question: string) => {
    if (!repoPath || !question.trim() || busy) return;

    const id = crypto.randomUUID();
    setMessages((prev) => [...prev, { id, question: question.trim(), status: "loading" }]);
    setInput("");
    setEvidenceLoading(true);

    const [retrieveOutcome, askOutcome] = await Promise.allSettled([
      retrieveChunks(repoPath, question, 6),
      askCodebase(repoPath, question, 6),
    ]);

    setEvidence(retrieveOutcome.status === "fulfilled" ? retrieveOutcome.value.results : []);
    setEvidenceLoading(false);

    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? askOutcome.status === "fulfilled"
            ? { ...m, status: "done", answer: askOutcome.value.answer, sources: askOutcome.value.sources, model: askOutcome.value.model }
            : { ...m, status: "error", error: askOutcome.reason }
          : m
      )
    );

    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    ask(input);
  };

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 overflow-auto scrollbar-thin px-5 py-5">
          {messages.length === 0 ? (
            <EmptyState
              icon={MessageSquareText}
              title="Ask anything about this codebase"
              description="Questions are answered from indexed code only, with file-level sources."
              className="mt-8"
            />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-6">
              {messages.map((m) => (
                <ChatMessage key={m.id} message={m} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}

          {messages.length === 0 && (
            <div className="mx-auto mt-4 flex max-w-3xl flex-wrap justify-center gap-2">
              {EXAMPLE_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => ask(p)}
                  className="rounded-full border border-base-600 bg-base-850 px-3 py-1.5 text-xs text-ink-400 transition-colors hover:border-accent-dim hover:text-ink-100"
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="shrink-0 border-t border-base-600 bg-base-850 p-3">
          <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about the codebase…"
              disabled={busy}
              className="flex-1 rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600 focus:border-accent-dim focus:outline-none disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent text-white transition-colors hover:bg-accent-dim disabled:cursor-not-allowed disabled:bg-base-700 disabled:text-ink-500"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      </div>

      <EvidenceDock results={evidence} loading={evidenceLoading} title="Evidence" />
    </div>
  );
}
