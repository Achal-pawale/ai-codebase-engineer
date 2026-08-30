import { Braces, FunctionSquare } from "lucide-react";
import type { CodeChunk, ScoredChunk } from "@/types/api";
import { cn, truncateMiddle } from "@/lib/utils";
import { LoadingState } from "@/components/ui/LoadingState";

interface EvidencePanelProps {
  results: ScoredChunk[];
  selectedChunkId?: number | null;
  onSelect: (chunk: CodeChunk) => void;
  loading?: boolean;
  title?: string;
}

export function EvidencePanel({ results, selectedChunkId, onSelect, loading, title = "Evidence" }: EvidencePanelProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-base-600 px-3 py-2.5">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-500">{title}</p>
      </div>

      <div className="flex-1 overflow-auto scrollbar-thin">
        {loading && <LoadingState message="Searching repository…" compact className="px-3 py-4" />}

        {!loading && results.length === 0 && (
          <p className="px-3 py-4 text-xs leading-relaxed text-ink-500">
            No matching code found yet. Ask a question to see the retrieved evidence here.
          </p>
        )}

        {!loading &&
          results.map(({ chunk }) => {
            const isSelected = chunk.chunk_id === selectedChunkId;
            const Icon = chunk.type === "class" ? Braces : FunctionSquare;

            return (
              <button
                key={chunk.chunk_id}
                onClick={() => onSelect(chunk)}
                className={cn(
                  "flex w-full items-start gap-2 border-b border-base-700/60 px-3 py-2.5 text-left transition-colors",
                  isSelected ? "bg-accent-soft" : "hover:bg-base-800"
                )}
              >
                <Icon size={13} className={cn("mt-0.5 shrink-0", isSelected ? "text-accent-bright" : "text-ink-500")} />
                <div className="min-w-0 flex-1">
                  <div className={cn("truncate font-mono text-xs font-medium", isSelected ? "text-accent-bright" : "text-ink-200")}>
                    {chunk.name}
                  </div>
                  <div className="mt-0.5 truncate font-mono text-[11px] text-ink-500" title={chunk.file}>
                    {truncateMiddle(chunk.file, 34)}:{chunk.start_line}
                    {chunk.end_line !== chunk.start_line ? `–${chunk.end_line}` : ""}
                  </div>
                </div>
              </button>
            );
          })}
      </div>
    </div>
  );
}
