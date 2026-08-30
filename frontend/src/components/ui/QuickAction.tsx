import type { LucideIcon } from "lucide-react";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface QuickActionProps {
  icon: LucideIcon;
  title: string;
  description: string;
  onClick: () => void;
  disabled?: boolean;
}

export function QuickAction({ icon: Icon, title, description, onClick, disabled }: QuickActionProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "group flex w-full items-start gap-3 rounded-lg border border-base-600 bg-base-850 p-4 text-left transition-colors",
        disabled ? "cursor-not-allowed opacity-50" : "hover:border-accent-dim hover:bg-base-800"
      )}
    >
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent-bright">
        <Icon size={16} strokeWidth={2} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-sm font-medium text-ink-100">
          {title}
          <ArrowUpRight size={13} className="text-ink-500 opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <div className="mt-0.5 text-xs leading-relaxed text-ink-400">{description}</div>
      </div>
    </button>
  );
}
