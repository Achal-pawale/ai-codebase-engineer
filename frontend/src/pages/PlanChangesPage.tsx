import { useState } from "react";
import { ClipboardList, FileCode2, ShieldAlert, TestTube2 } from "lucide-react";
import { useRepository } from "@/state/RepositoryContext";
import { retrieveChunks } from "@/api/repository";
import { planFeature } from "@/api/planning";
import type { PlanResponse, ScoredChunk } from "@/types/api";
import { parseHeadedSections, PLAN_HEADERS } from "@/lib/parseSections";
import { EvidenceDock } from "@/components/code/EvidenceDock";
import { SectionCard } from "@/components/ui/SectionCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatAnswerHtml } from "@/lib/formatAnswer";
import { truncateMiddle } from "@/lib/utils";

type Status = "idle" | "loading" | "done" | "error";

const SECTION_ICONS: Record<string, typeof FileCode2> = {
  "AFFECTED FILES": FileCode2,
  "PROPOSED CHANGES": ClipboardList,
  RISKS: ShieldAlert,
  "TESTS TO CONSIDER": TestTube2,
};

export function PlanChangesPage() {
  const { repoPath } = useRepository();
  const [request, setRequest] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [evidence, setEvidence] = useState<ScoredChunk[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const runPlan = async () => {
    if (!repoPath || !request.trim() || status === "loading") return;

    setStatus("loading");
    setError(null);
    setEvidenceLoading(true);

    const [retrieveOutcome, planOutcome] = await Promise.allSettled([
      retrieveChunks(repoPath, request, 6),
      planFeature(repoPath, request, 6),
    ]);

    setEvidence(retrieveOutcome.status === "fulfilled" ? retrieveOutcome.value.results : []);
    setEvidenceLoading(false);

    if (planOutcome.status === "fulfilled") {
      setResult(planOutcome.value);
      setStatus("done");
    } else {
      setError(planOutcome.reason);
      setStatus("error");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runPlan();
  };

  const sections = result ? parseHeadedSections(result.plan, PLAN_HEADERS) : [];

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <div className="min-h-0 flex-1 overflow-auto scrollbar-thin px-5 py-5">
        <div className="mx-auto max-w-3xl">
          <form onSubmit={handleSubmit} className="rounded-lg border border-base-600 bg-base-850 p-4">
            <label className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-ink-500">
              <ClipboardList size={13} />
              Describe the feature or change
            </label>
            <textarea
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="e.g. Add rate limiting to the /ask endpoint."
              rows={3}
              disabled={status === "loading"}
              className="mt-2 w-full resize-none rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600 focus:border-accent-dim focus:outline-none disabled:opacity-60"
            />
            <div className="mt-3 flex justify-end">
              <button
                type="submit"
                disabled={status === "loading" || !request.trim()}
                className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-dim disabled:cursor-not-allowed disabled:bg-base-700 disabled:text-ink-500"
              >
                {status === "loading" ? "Planning…" : "Generate Plan"}
              </button>
            </div>
          </form>

          <div className="mt-5 flex flex-col gap-3">
            {status === "idle" && (
              <EmptyState
                icon={ClipboardList}
                title="No plan yet"
                description="Describe a feature or change above to get an implementation plan grounded in the indexed code."
              />
            )}

            {status === "loading" && <LoadingState message="Creating implementation plan…" submessage="Retrieving relevant code and drafting an approach." />}

            {status === "error" && <ErrorState error={error} onRetry={runPlan} />}

            {status === "done" && result && (
              <>
                <p className="px-1 text-xs leading-relaxed text-ink-600">
                  Shown as returned by the model, grouped under its own headings. Structured per-step complexity
                  ratings aren't returned by the backend yet — see{" "}
                  <span className="font-mono text-ink-500">RISKS</span> below for a qualitative read instead.
                </p>

                {sections.map((section) => {
                  const Icon = SECTION_ICONS[section.heading.toUpperCase()] ?? ClipboardList;
                  return (
                    <SectionCard key={section.heading} title={section.heading} icon={Icon}>
                      <div
                        className="whitespace-pre-wrap text-sm leading-relaxed text-ink-200"
                        dangerouslySetInnerHTML={{ __html: formatAnswerHtml(section.body) }}
                      />
                    </SectionCard>
                  );
                })}

                {result.sources.length > 0 && (
                  <SectionCard title="Sources" icon={FileCode2}>
                    <div className="flex flex-wrap gap-1.5">
                      {result.sources.map((s) => (
                        <span key={s} className="rounded bg-base-700 px-1.5 py-0.5 font-mono text-[11px] text-ink-400">
                          {truncateMiddle(s, 32)}
                        </span>
                      ))}
                    </div>
                  </SectionCard>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <EvidenceDock results={evidence} loading={evidenceLoading} title="Evidence" />
    </div>
  );
}
