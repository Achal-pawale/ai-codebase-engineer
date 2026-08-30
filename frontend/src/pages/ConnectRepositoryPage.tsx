import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Github, Loader2, WifiOff } from "lucide-react";
import { Logo } from "@/components/layout/Logo";
import { useRepository, type ConnectionStage } from "@/state/RepositoryContext";
import { useBackendStatus } from "@/hooks/useBackendStatus";
import { cn } from "@/lib/utils";

const STAGES: { key: ConnectionStage; label: string }[] = [
  { key: "connecting", label: "Connecting" },
  { key: "cloning", label: "Cloning repository" },
  { key: "analyzing", label: "Analyzing codebase" },
  { key: "indexing", label: "Indexing & mapping relationships" },
  { key: "ready", label: "Ready" },
];

export function ConnectRepositoryPage() {
  const [url, setUrl] = useState("");
  const { connect, status, stage, error, repoLabel, isReady } = useRepository();
  const backendStatus = useBackendStatus();
  const navigate = useNavigate();

  useEffect(() => {
    if (isReady) navigate("/overview", { replace: true });
  }, [isReady, navigate]);

  const currentIndex = stage ? STAGES.findIndex((s) => s.key === stage) : -1;
  const isWorking = status === "working";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() || isWorking) return;
    connect(url.trim());
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-base-900 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo size={32} />
          <h1 className="mt-4 text-lg font-semibold text-ink-100">Connect a GitHub repository</h1>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-500">
            Clone, analyze, and index a public repository so the engineer can answer questions grounded in its
            actual code.
          </p>
        </div>

        <div className="rounded-lg border border-base-600 bg-base-850 p-5 shadow-panel">
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="text-xs font-medium text-ink-400" htmlFor="repo-url">
              GitHub repository URL
            </label>
            <div className="flex items-center gap-2 rounded-md border border-base-600 bg-base-900 px-3 py-2 focus-within:border-accent-dim">
              <Github size={15} className="shrink-0 text-ink-500" />
              <input
                id="repo-url"
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/user/repository"
                disabled={isWorking}
                className="w-full bg-transparent font-mono text-sm text-ink-100 placeholder:text-ink-600 focus:outline-none disabled:opacity-60"
              />
            </div>

            <button
              type="submit"
              disabled={isWorking || !url.trim() || backendStatus === "offline"}
              className="mt-1 flex items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-dim disabled:cursor-not-allowed disabled:bg-base-700 disabled:text-ink-500"
            >
              {isWorking && <Loader2 size={14} className="animate-spin" />}
              {isWorking ? "Analyzing…" : "Analyze Repository"}
            </button>
          </form>

          {backendStatus === "offline" && (
            <div className="mt-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-ink-200">
              <WifiOff size={14} className="mt-0.5 shrink-0 text-danger" />
              <div>
                <p className="font-medium text-danger">Backend unreachable</p>
                <p className="mt-0.5 text-ink-400">
                  Start the FastAPI server (<code className="font-mono">uvicorn app.main:app</code>) and try again.
                </p>
              </div>
            </div>
          )}

          {(isWorking || status === "ready") && (
            <ul className="mt-5 flex flex-col gap-2 border-t border-base-700 pt-4">
              {STAGES.map((s, idx) => {
                const done = status === "ready" || idx < currentIndex || (idx === currentIndex && s.key === "ready");
                const active = idx === currentIndex && status !== "ready";

                return (
                  <li key={s.key} className="flex items-center gap-2.5 text-xs">
                    <span
                      className={cn(
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded-full",
                        done ? "bg-ok text-base-900" : active ? "bg-accent-soft text-accent" : "bg-base-700 text-ink-600"
                      )}
                    >
                      {done ? <Check size={10} strokeWidth={3} /> : active ? <Loader2 size={10} className="animate-spin" /> : null}
                    </span>
                    <span className={cn(done ? "text-ink-300" : active ? "text-ink-100" : "text-ink-600")}>{s.label}</span>
                  </li>
                );
              })}
            </ul>
          )}

          {status === "error" && error && (
            <div className="mt-4 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-xs">
              <p className="font-medium text-danger">Couldn't connect {repoLabel ?? "repository"}</p>
              <p className="mt-1 leading-relaxed text-ink-300">{error}</p>
            </div>
          )}
        </div>

        <p className="mt-4 text-center text-xs text-ink-600">
          Works with any public GitHub repository. The engineer currently parses Python files for structural
          analysis.
        </p>
      </div>
    </div>
  );
}
