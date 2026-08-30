import { useEffect, useState } from "react";
import { CheckCircle2, CircleSlash, FlaskConical, PlayCircle, Terminal, XCircle } from "lucide-react";
import { useRepository } from "@/state/RepositoryContext";
import { detectTests, validateRepository } from "@/api/tests";
import type { DetectTestsResponse, ValidateResponse } from "@/types/api";
import { parsePytestOutput } from "@/lib/parseTestOutput";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SectionCard } from "@/components/ui/SectionCard";

type DetectStatus = "loading" | "done" | "error";
type RunStatus = "idle" | "running" | "done" | "error";

export function TestsPage() {
  const { repoPath } = useRepository();
  const [detectStatus, setDetectStatus] = useState<DetectStatus>("loading");
  const [detection, setDetection] = useState<DetectTestsResponse | null>(null);
  const [detectError, setDetectError] = useState<unknown>(null);

  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [result, setResult] = useState<ValidateResponse | null>(null);
  const [runError, setRunError] = useState<unknown>(null);

  const runDetect = async () => {
    if (!repoPath) return;
    setDetectStatus("loading");
    try {
      const res = await detectTests(repoPath);
      setDetection(res);
      setDetectStatus("done");
    } catch (error) {
      setDetectError(error);
      setDetectStatus("error");
    }
  };

  useEffect(() => {
    runDetect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoPath]);

  const runValidate = async () => {
    if (!repoPath || runStatus === "running") return;
    setRunStatus("running");
    setRunError(null);

    try {
      const res = await validateRepository(repoPath);
      setResult(res);
      setRunStatus("done");
    } catch (error) {
      setRunError(error);
      setRunStatus("error");
    }
  };

  const ran = result && "stdout" in result ? result : null;
  const noFramework = result && "message" in result ? result : null;
  const failedRun = result && !result.success && "error" in result ? result : null;

  const parsed = ran && ran.framework?.toLowerCase().includes("pytest") ? parsePytestOutput(ran.stdout) : null;

  return (
    <div className="mx-auto max-w-4xl px-5 py-5">
      <SectionCard
        title="Test framework"
        icon={FlaskConical}
        right={
          detectStatus === "done" && detection ? (
            <StatusBadge label={detection.detected ? `Detected · ${detection.framework}` : "Not detected"} tone={detection.detected ? "ok" : "neutral"} />
          ) : undefined
        }
      >
        {detectStatus === "loading" && <LoadingState message="Detecting test framework…" compact />}
        {detectStatus === "error" && <ErrorState error={detectError} onRetry={runDetect} compact />}

        {detectStatus === "done" && detection && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-ink-500">
              {detection.detected ? (
                <>
                  Run command: <span className="font-mono text-ink-300">{detection.command}</span>
                </>
              ) : (
                "No recognized test configuration (pytest, package.json test script, etc.) was found in this repository."
              )}
            </div>
            <button
              onClick={runValidate}
              disabled={!detection.detected || runStatus === "running"}
              className="flex shrink-0 items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-dim disabled:cursor-not-allowed disabled:bg-base-700 disabled:text-ink-500"
            >
              <PlayCircle size={13} />
              {runStatus === "running" ? "Running…" : "Run Tests"}
            </button>
          </div>
        )}
      </SectionCard>

      <div className="mt-4">
        {runStatus === "idle" && !result && (
          <div className="rounded-lg border border-dashed border-base-600 py-10 text-center text-sm text-ink-500">
            Run the test suite to see results here.
          </div>
        )}

        {runStatus === "running" && <LoadingState message="Running tests…" submessage="This runs the detected command in the cloned repository — it can take a while." />}

        {runStatus === "error" && <ErrorState error={runError} onRetry={runValidate} />}

        {runStatus === "done" && noFramework && (
          <div className="flex items-start gap-2 rounded-lg border border-base-600 bg-base-850 px-4 py-3 text-sm text-ink-300">
            <CircleSlash size={15} className="mt-0.5 shrink-0 text-ink-500" />
            {noFramework.message}
          </div>
        )}

        {runStatus === "done" && failedRun && (
          <ErrorState
            error={new Error(failedRun.error)}
            onRetry={runValidate}
          />
        )}

        {runStatus === "done" && ran && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 rounded-lg border border-base-600 bg-base-850 px-4 py-3">
              {ran.passed ? (
                <CheckCircle2 size={16} className="text-ok" />
              ) : (
                <XCircle size={16} className="text-danger" />
              )}
              <span className="text-sm font-medium text-ink-100">{ran.passed ? "Tests passed" : "Tests failed"}</span>
              <span className="ml-auto font-mono text-xs text-ink-500">
                {ran.framework} · exit code {ran.return_code}
              </span>
            </div>

            {parsed?.counts && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard icon={CheckCircle2} label="Passed" value={parsed.counts.passed} />
                <StatCard icon={XCircle} label="Failed" value={parsed.counts.failed} />
                <StatCard icon={CircleSlash} label="Skipped" value={parsed.counts.skipped} />
                <StatCard icon={FlaskConical} label="Total" value={parsed.counts.total} sublabel={parsed.durationSeconds ? `${parsed.durationSeconds}s` : undefined} />
              </div>
            )}

            {parsed && parsed.failedTests.length > 0 && (
              <SectionCard title="Failed tests" icon={XCircle}>
                <ul className="flex flex-col gap-1">
                  {parsed.failedTests.map((t) => (
                    <li key={t} className="font-mono text-xs text-danger">
                      {t}
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}

            {!parsed && (
              <p className="text-xs text-ink-600">
                Per-test breakdown parsing is only implemented for pytest output — showing the raw log below for this
                framework.
              </p>
            )}

            <SectionCard title="Output" icon={Terminal}>
              <pre className="max-h-80 overflow-auto scrollbar-thin whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-ink-300">
                {ran.stdout || "(no stdout)"}
              </pre>
              {ran.stderr && (
                <pre className="mt-3 max-h-40 overflow-auto scrollbar-thin whitespace-pre-wrap border-t border-base-700 pt-3 font-mono text-[12px] leading-relaxed text-danger/90">
                  {ran.stderr}
                </pre>
              )}
            </SectionCard>
          </div>
        )}
      </div>
    </div>
  );
}
