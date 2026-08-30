import { useState } from "react";
import { AlertCircle, Bug, FileWarning, Gauge, ListChecks, Wrench } from "lucide-react";
import { useRepository } from "@/state/RepositoryContext";
import { retrieveChunks } from "@/api/repository";
import { investigateBug } from "@/api/investigation";
import type { InvestigateResponse, ScoredChunk } from "@/types/api";
import { extractConfidence, INVESTIGATE_HEADERS, parseHeadedSections } from "@/lib/parseSections";
import { EvidenceDock } from "@/components/code/EvidenceDock";
import { SectionCard } from "@/components/ui/SectionCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatAnswerHtml } from "@/lib/formatAnswer";
import { truncateMiddle } from "@/lib/utils";

type Status = "idle" | "loading" | "done" | "error";

const CONFIDENCE_TONE = { High: "ok", Medium: "warn", Low: "danger" } as const;

export function InvestigatePage() {
  const { repoPath } = useRepository();
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<InvestigateResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [evidence, setEvidence] = useState<ScoredChunk[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const runInvestigation = async () => {
    if (!repoPath || !description.trim() || status === "loading") return;

    setStatus("loading");
    setError(null);
    setEvidenceLoading(true);

    const [retrieveOutcome, investigateOutcome] = await Promise.allSettled([
      retrieveChunks(repoPath, description, 6),
      investigateBug(repoPath, description, 6),
    ]);

    setEvidence(retrieveOutcome.status === "fulfilled" ? retrieveOutcome.value.results : []);
    setEvidenceLoading(false);

    if (investigateOutcome.status === "fulfilled") {
      setResult(investigateOutcome.value);
      setStatus("done");
    } else {
      setError(investigateOutcome.reason);
      setStatus("error");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runInvestigation();
  };

  const sections = result ? parseHeadedSections(result.investigation, INVESTIGATE_HEADERS) : [];
  const cause = sections.find((s) => s.heading.toUpperCase() === "SUSPECTED CAUSE");
  const modelEvidence = sections.find((s) => s.heading.toUpperCase() === "EVIDENCE");
  const filesToCheck = sections.find((s) => s.heading.toUpperCase() === "FILES TO CHECK NEXT");
  const fallback = sections.find((s) => s.heading === "Response");
  const confidence = result ? extractConfidence(sections) : null;

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <div className="min-h-0 flex-1 overflow-auto scrollbar-thin px-5 py-5">
        <div className="mx-auto max-w-3xl">
          <form onSubmit={handleSubmit} className="rounded-lg border border-base-600 bg-base-850 p-4">
            <label className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-ink-500">
              <Bug size={13} />
              Describe the bug or problem
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Users receive a 500 error during repository indexing."
              rows={3}
              disabled={status === "loading"}
              className="mt-2 w-full resize-none rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600 focus:border-accent-dim focus:outline-none disabled:opacity-60"
            />
            <div className="mt-3 flex justify-end">
              <button
                type="submit"
                disabled={status === "loading" || !description.trim()}
                className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-dim disabled:cursor-not-allowed disabled:bg-base-700 disabled:text-ink-500"
              >
                {status === "loading" ? "Investigating…" : "Investigate"}
              </button>
            </div>
          </form>

          <div className="mt-5 flex flex-col gap-3">
            {status === "idle" && (
              <EmptyState
                icon={Bug}
                title="No investigation yet"
                description="Describe a bug above and the engineer will trace it through the indexed code."
              />
            )}

            {status === "loading" && <LoadingState message="Investigating issue…" submessage="Retrieving relevant code and reasoning about the likely cause." />}

            {status === "error" && <ErrorState error={error} onRetry={runInvestigation} />}

            {status === "done" && result && (
              <>
                <SectionCard
                  title="Investigation summary"
                  icon={AlertCircle}
                  right={confidence && <StatusBadge label={`${confidence} confidence`} tone={CONFIDENCE_TONE[confidence]} />}
                >
                  {cause ? (
                    <div
                      className="whitespace-pre-wrap text-sm leading-relaxed text-ink-200"
                      dangerouslySetInnerHTML={{ __html: formatAnswerHtml(cause.body) }}
                    />
                  ) : fallback ? (
                    <div
                      className="whitespace-pre-wrap text-sm leading-relaxed text-ink-200"
                      dangerouslySetInnerHTML={{ __html: formatAnswerHtml(fallback.body) }}
                    />
                  ) : (
                    <p className="text-sm text-ink-500">No cause could be parsed from the model's response.</p>
                  )}
                </SectionCard>

                {modelEvidence && (
                  <SectionCard title="Supporting evidence" icon={ListChecks}>
                    <div
                      className="whitespace-pre-wrap text-sm leading-relaxed text-ink-300"
                      dangerouslySetInnerHTML={{ __html: formatAnswerHtml(modelEvidence.body) }}
                    />
                  </SectionCard>
                )}

                <SectionCard title="Relevant files" icon={FileWarning}>
                  {filesToCheck ? (
                    <div
                      className="whitespace-pre-wrap text-sm leading-relaxed text-ink-300"
                      dangerouslySetInnerHTML={{ __html: formatAnswerHtml(filesToCheck.body) }}
                    />
                  ) : result.sources.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {result.sources.map((s) => (
                        <span key={s} className="rounded bg-base-700 px-1.5 py-0.5 font-mono text-[11px] text-ink-400">
                          {truncateMiddle(s, 32)}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-ink-500">No specific files were called out.</p>
                  )}
                </SectionCard>

                <SectionCard title="Suggested fix" icon={Wrench} muted>
                  <p className="text-xs leading-relaxed text-ink-500">
                    Coming soon — the backend's /investigate endpoint returns a suspected cause and evidence, but
                    doesn't yet generate a concrete remediation separate from the cause above. Use{" "}
                    <span className="font-mono text-ink-400">Plan Changes</span> to turn this into an implementation
                    plan once the cause is confirmed.
                  </p>
                </SectionCard>

                <SectionCard title="Request / execution flow" icon={Gauge} muted>
                  <p className="text-xs leading-relaxed text-ink-500">
                    Coming soon — tracing an actual execution path requires runtime or call-graph data the backend
                    doesn't collect yet; today's investigation is based on static code retrieval only.
                  </p>
                </SectionCard>
              </>
            )}
          </div>
        </div>
      </div>

      <EvidenceDock results={evidence} loading={evidenceLoading} title="Evidence" />
    </div>
  );
}
