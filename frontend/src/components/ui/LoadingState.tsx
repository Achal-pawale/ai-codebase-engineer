import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoadingStateProps {
  message: string;
  submessage?: string;
  className?: string;
  compact?: boolean;
}

export function LoadingState({ message, submessage, className, compact = false }: LoadingStateProps) {
  if (compact) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-ink-400", className)}>
        <Loader2 size={14} className="animate-spin text-accent" />
        {message}
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 py-16 text-center", className)}>
      <Loader2 size={22} className="animate-spin text-accent" />
      <div>
        <p className="text-sm font-medium text-ink-200">{message}</p>
        {submessage && <p className="mt-1 text-xs text-ink-500">{submessage}</p>}
      </div>
    </div>
  );
}
