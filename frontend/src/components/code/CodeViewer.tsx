import { useState } from "react";
import { Check, Copy, FileCode2, X } from "lucide-react";
import { highlightLine, languageForExtension } from "@/lib/highlight";
import { cn, truncateMiddle } from "@/lib/utils";

interface CodeViewerProps {
  filePath: string;
  startLine: number;
  endLine: number;
  content: string;
  symbolName?: string;
  symbolType?: string;
  onClose?: () => void;
  className?: string;
}

export function CodeViewer({
  filePath,
  startLine,
  endLine,
  content,
  symbolName,
  symbolType,
  onClose,
  className,
}: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const extension = "." + (filePath.split(".").pop() ?? "");
  const language = languageForExtension(extension);
  const lines = content.split("\n");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can be unavailable (e.g. insecure context) — fail quietly.
    }
  };

  return (
    <div className={cn("flex h-full flex-col overflow-hidden rounded-lg border border-base-600 bg-base-900", className)}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-base-600 bg-base-850 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <FileCode2 size={14} className="shrink-0 text-ink-500" />
          <span className="truncate font-mono text-xs text-ink-200" title={filePath}>
            {truncateMiddle(filePath, 44)}
          </span>
          <span className="shrink-0 font-mono text-xs text-ink-500">
            L{startLine}
            {endLine !== startLine ? `–${endLine}` : ""}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {symbolType && (
            <span className="rounded bg-base-700 px-1.5 py-0.5 font-mono text-[11px] text-ink-400">{symbolType}</span>
          )}
          <span className="rounded bg-base-700 px-1.5 py-0.5 font-mono text-[11px] uppercase text-ink-400">{language}</span>
          <button
            onClick={handleCopy}
            title="Copy code"
            className="flex h-6 w-6 items-center justify-center rounded text-ink-400 transition-colors hover:bg-base-700 hover:text-ink-100"
          >
            {copied ? <Check size={13} className="text-ok" /> : <Copy size={13} />}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              title="Close"
              className="flex h-6 w-6 items-center justify-center rounded text-ink-400 transition-colors hover:bg-base-700 hover:text-ink-100"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {symbolName && (
        <div className="shrink-0 border-b border-base-600 bg-base-850/60 px-3 py-1.5 font-mono text-xs text-ink-400">
          {symbolType ?? "symbol"} <span className="text-accent-bright">{symbolName}</span>
        </div>
      )}

      <div className="flex-1 overflow-auto scrollbar-thin">
        <pre className="min-w-max px-0 py-2 font-mono text-[12.5px] leading-[1.55]">
          <code>
            {lines.map((line, idx) => (
              <div key={idx} className="flex hover:bg-base-800/60">
                <span className="sticky left-0 w-12 shrink-0 select-none border-r border-base-700/70 bg-base-900 px-2 text-right text-ink-600">
                  {startLine + idx}
                </span>
                <span
                  className="flex-1 whitespace-pre px-3 text-ink-200"
                  dangerouslySetInnerHTML={{ __html: highlightLine(line, language) || "&nbsp;" }}
                />
              </div>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}
