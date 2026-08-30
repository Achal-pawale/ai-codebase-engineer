import { useState } from "react";
import type { CodeChunk, ScoredChunk } from "@/types/api";
import { EvidencePanel } from "./EvidencePanel";
import { CodeViewer } from "./CodeViewer";

interface EvidenceDockProps {
  results: ScoredChunk[];
  loading?: boolean;
  title?: string;
}

/** Right-hand (desktop) / below-content (mobile) dock: evidence list that swaps to a code viewer on selection. */
export function EvidenceDock({ results, loading, title }: EvidenceDockProps) {
  const [selected, setSelected] = useState<CodeChunk | null>(null);

  return (
    <aside className="flex h-full min-h-[280px] w-full flex-col border-t border-base-600 lg:w-[340px] lg:shrink-0 lg:border-l lg:border-t-0">
      {selected ? (
        <div className="flex h-full flex-col p-2">
          <CodeViewer
            filePath={selected.file}
            startLine={selected.start_line}
            endLine={selected.end_line}
            content={selected.content}
            symbolName={selected.name}
            symbolType={selected.type}
            onClose={() => setSelected(null)}
          />
        </div>
      ) : (
        <EvidencePanel results={results} loading={loading} onSelect={setSelected} title={title} />
      )}
    </aside>
  );
}
