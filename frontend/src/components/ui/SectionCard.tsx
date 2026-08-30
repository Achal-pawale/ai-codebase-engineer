import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SectionCardProps {
  title: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
  right?: React.ReactNode;
  muted?: boolean;
}

export function SectionCard({ title, icon: Icon, children, className, right, muted = false }: SectionCardProps) {
  return (
    <div className={cn("rounded-lg border border-base-600 bg-base-850", muted && "opacity-70", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-base-700 px-4 py-2.5">
        <div className="flex items-center gap-2 text-ink-300">
          {Icon && <Icon size={13} className="text-ink-500" />}
          <span className="text-xs font-medium uppercase tracking-wide">{title}</span>
        </div>
        {right}
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}
