import { useMemo } from "react";
import { FileDiff } from "lucide-react";
import { cn } from "@/lib/utils";

interface DiffViewerProps {
  diff: string;
  filePath: string;
  className?: string;
}

interface DiffLine {
  kind: "add" | "remove" | "hunk" | "meta" | "context";
  text: string;
}

function parseDiff(diff: string): { lines: DiffLine[]; additions: number; deletions: number } {
  const rawLines = diff.split("\n");
  const lines: DiffLine[] = [];
  let additions = 0;
  let deletions = 0;

  for (const line of rawLines) {
    if (line.startsWith("+++") || line.startsWith("---")) {
      lines.push({ kind: "meta", text: line });
    } else if (line.startsWith("@@")) {
      lines.push({ kind: "hunk", text: line });
    } else if (line.startsWith("+")) {
      additions += 1;
      lines.push({ kind: "add", text: line });
    } else if (line.startsWith("-")) {
      deletions += 1;
      lines.push({ kind: "remove", text: line });
    } else if (line.length > 0) {
      lines.push({ kind: "context", text: line });
    }
  }

  return { lines, additions, deletions };
}

const KIND_STYLES: Record<DiffLine["kind"], string> = {
  add: "bg-ok-soft text-ink-100 before:content-['+'] before:text-ok before:mr-2",
  remove: "bg-danger-soft text-ink-100 before:content-['−'] before:text-danger before:mr-2",
  hunk: "text-accent-bright bg-accent-soft/60",
  meta: "text-ink-500",
  context: "text-ink-300 before:content-['\\00a0'] before:mr-2",
};

export function DiffViewer({ diff, filePath, className }: DiffViewerProps) {
  const { lines, additions, deletions } = useMemo(() => parseDiff(diff), [diff]);

  return (
    <div className={cn("overflow-hidden rounded-lg border border-base-600 bg-base-900", className)}>
      <div className="flex items-center justify-between border-b border-base-600 bg-base-850 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <FileDiff size={14} className="shrink-0 text-ink-500" />
          <span className="truncate font-mono text-xs text-ink-200">{filePath}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2 font-mono text-xs">
          <span className="text-ok">+{additions}</span>
          <span className="text-danger">−{deletions}</span>
        </div>
      </div>
      <div className="max-h-[420px] overflow-auto scrollbar-thin">
        <pre className="min-w-max px-3 py-2 font-mono text-[12.5px] leading-[1.6]">
          {lines.map((line, idx) => (
            <div key={idx} className={cn("whitespace-pre px-1", KIND_STYLES[line.kind])}>
              {line.kind === "add" || line.kind === "remove" ? line.text.slice(1) : line.text}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
