import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import { ApiError } from "@/types/api";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}

function messageFor(error: unknown): { title: string; detail: string; icon: typeof AlertTriangle } {
  if (error instanceof ApiError) {
    if (error.kind === "network") return { title: "Backend unreachable", detail: error.message, icon: WifiOff };
    if (error.kind === "timeout") return { title: "Request timed out", detail: error.message, icon: WifiOff };
    if (error.kind === "rate_limit") return { title: "Rate limited", detail: error.message, icon: AlertTriangle };
    if (error.kind === "validation") return { title: "Invalid request", detail: error.message, icon: AlertTriangle };
    return { title: "Backend error", detail: error.message, icon: AlertTriangle };
  }

  if (error instanceof Error) {
    return { title: "Something went wrong", detail: error.message, icon: AlertTriangle };
  }

  return { title: "Something went wrong", detail: "An unexpected error occurred.", icon: AlertTriangle };
}

export function ErrorState({ error, onRetry, className, compact = false }: ErrorStateProps) {
  const { title, detail, icon: Icon } = messageFor(error);

  if (compact) {
    return (
      <div className={cn("flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-ink-200", className)}>
        <Icon size={14} className="mt-0.5 shrink-0 text-danger" />
        <div className="min-w-0">
          <p className="font-medium text-danger">{title}</p>
          <p className="mt-0.5 text-ink-400">{detail}</p>
        </div>
        {onRetry && (
          <button onClick={onRetry} className="ml-auto shrink-0 text-ink-400 hover:text-ink-100" title="Retry">
            <RefreshCw size={13} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 rounded-lg border border-danger/30 bg-danger-soft py-14 text-center", className)}>
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-base-900 text-danger">
        <Icon size={18} strokeWidth={1.75} />
      </div>
      <div className="max-w-sm">
        <p className="text-sm font-medium text-ink-100">{title}</p>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">{detail}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 inline-flex items-center gap-1.5 rounded-md border border-base-600 bg-base-800 px-3 py-1.5 text-xs font-medium text-ink-200 transition-colors hover:border-accent-dim hover:text-ink-100"
        >
          <RefreshCw size={12} />
          Try again
        </button>
      )}
    </div>
  );
}
