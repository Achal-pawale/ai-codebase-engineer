import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sublabel?: string;
  className?: string;
}

export function StatCard({ icon: Icon, label, value, sublabel, className }: StatCardProps) {
  return (
    <div className={cn("rounded-lg border border-base-600 bg-base-850 p-4", className)}>
      <div className="flex items-center gap-2 text-ink-500">
        <Icon size={14} strokeWidth={2} />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className="mt-2 font-mono text-2xl font-semibold text-ink-100">{value}</div>
      {sublabel && <div className="mt-0.5 text-xs text-ink-500">{sublabel}</div>}
    </div>
  );
}
