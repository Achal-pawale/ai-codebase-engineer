import { useState } from "react";
import { Check, FileCode2, GitPullRequest, Info, Save, X } from "lucide-react";
import { useRepository } from "@/state/RepositoryContext";
import { proposeChange } from "@/api/changes";
import type { ProposeChangeSuccess } from "@/types/api";
import { ApiError } from "@/types/api";
import { DiffViewer } from "@/components/code/DiffViewer";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";

interface ProposalEntry {
  id: string;
  filePath: string;
  instruction: string;
  status: "loading" | "done" | "error";
  response?: ProposeChangeSuccess;
  error?: unknown;
}

export function ProposedChangesPage() {
  const { repoPath } = useRepository();
  const [filePath, setFilePath] = useState("");
  const [instruction, setInstruction] = useState("");
  const [entries, setEntries] = useState<ProposalEntry[]>([]);

  const busy = entries.some((e) => e.status === "loading");

  const submit = async () => {
    if (!repoPath || !filePath.trim() || !instruction.trim() || busy) return;

    const id = crypto.randomUUID();
    const targetFile = filePath.trim();
    const targetInstruction = instruction.trim();

    setEntries((prev) => [{ id, filePath: targetFile, instruction: targetInstruction, status: "loading" }, ...prev]);
    setInstruction("");

    try {
      const res = await proposeChange(repoPath, targetFile, targetInstruction);

      setEntries((prev) =>
        prev.map((e) =>
          e.id === id
            ? res.success
              ? { ...e, status: "done", response: res }
              : { ...e, status: "error", error: new ApiError("http", res.error) }
            : e
        )
      );
    } catch (error) {
      setEntries((prev) => (prev.map((e) => (e.id === id ? { ...e, status: "error", error } : e))));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submit();
  };

  return (
    <div className="mx-auto max-w-3xl px-5 py-5">
      <form onSubmit={handleSubmit} className="rounded-lg border border-base-600 bg-base-850 p-4">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-ink-500">
          <GitPullRequest size={13} />
          Propose a code change
        </div>

        <div className="mt-2 flex flex-col gap-2">
          <input
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            placeholder="File path, e.g. backend/app/main.py"
            disabled={busy}
            className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 font-mono text-sm text-ink-100 placeholder:text-ink-600 focus:border-accent-dim focus:outline-none disabled:opacity-60"
          />
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Instruction, e.g. Add input validation for an empty repo_url."
            rows={3}
            disabled={busy}
            className="w-full resize-none rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600 focus:border-accent-dim focus:outline-none disabled:opacity-60"
          />
        </div>

        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={busy || !filePath.trim() || !instruction.trim()}
            className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-dim disabled:cursor-not-allowed disabled:bg-base-700 disabled:text-ink-500"
          >
            {busy ? "Generating…" : "Propose Change"}
          </button>
        </div>
      </form>

      <div className="mt-5 flex flex-col gap-4">
        {entries.length === 0 && (
          <EmptyState
            icon={GitPullRequest}
            title="No proposed changes yet"
            description="Point at a file and describe what should change — the model rewrites the file and shows a diff."
          />
        )}

        {entries.map((entry) => (
          <div key={entry.id} className="rounded-lg border border-base-600 bg-base-850">
            <div className="flex items-center justify-between gap-2 border-b border-base-700 px-4 py-2.5">
              <div className="flex min-w-0 items-center gap-2">
                <FileCode2 size={13} className="shrink-0 text-ink-500" />
                <span className="truncate font-mono text-xs text-ink-200">{entry.filePath}</span>
              </div>
              {entry.status === "done" && entry.response && (
                <StatusBadge label={entry.response.changed ? "Changed" : "No change needed"} tone={entry.response.changed ? "accent" : "neutral"} />
              )}
            </div>

            <div className="px-4 py-3">
              <p className="mb-2.5 text-xs text-ink-500">
                Instruction: <span className="text-ink-300">{entry.instruction}</span>
              </p>

              {entry.status === "loading" && <LoadingState message="Generating proposed change…" compact />}
              {entry.status === "error" && <ErrorState error={entry.error} compact />}

              {entry.status === "done" && entry.response && (
                <>
                  {entry.response.changed ? (
                    <DiffViewer diff={entry.response.diff} filePath={entry.response.file_path} />
                  ) : (
                    <div className="flex items-start gap-2 rounded-md border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-400">
                      <Info size={13} className="mt-0.5 shrink-0 text-ink-500" />
                      {entry.response.message || "The model determined no change was necessary for this instruction."}
                    </div>
                  )}

                  {entry.response.changed && entry.response.proposed_file_saved_to && (
                    <div className="mt-2 flex items-center gap-1.5 font-mono text-[11px] text-ink-600">
                      <Save size={11} />
                      Saved to {entry.response.proposed_file_saved_to}
                    </div>
                  )}

                  <div className="mt-3 flex items-center justify-between border-t border-base-700 pt-3">
                    <span className="text-[11px] text-ink-600">Risk level not assessed by backend</span>
                    <div className="flex items-center gap-2">
                      <button
                        disabled
                        title="Not yet supported — the backend has no endpoint to apply a proposed change"
                        className="flex cursor-not-allowed items-center gap-1.5 rounded-md border border-base-600 px-2.5 py-1 text-xs text-ink-600 opacity-60"
                      >
                        <Check size={12} />
                        Approve
                      </button>
                      <button
                        disabled
                        title="Not yet supported — the backend has no endpoint to discard a proposed change"
                        className="flex cursor-not-allowed items-center gap-1.5 rounded-md border border-base-600 px-2.5 py-1 text-xs text-ink-600 opacity-60"
                      >
                        <X size={12} />
                        Reject
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
