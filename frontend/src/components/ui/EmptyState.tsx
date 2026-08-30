import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-base-600 py-16 text-center", className)}>
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-base-800 text-ink-500">
        <Icon size={18} strokeWidth={1.75} />
      </div>
      <div className="max-w-sm">
        <p className="text-sm font-medium text-ink-200">{title}</p>
        <p className="mt-1 text-xs leading-relaxed text-ink-500">{description}</p>
      </div>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-1 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-dim"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
