import { cn } from "@/lib/utils";

export type Tone = "ok" | "warn" | "danger" | "accent" | "neutral";

const TONE_STYLES: Record<Tone, { dot: string; text: string; bg: string }> = {
  ok: { dot: "bg-ok", text: "text-ok", bg: "bg-ok-soft" },
  warn: { dot: "bg-warn", text: "text-warn", bg: "bg-warn-soft" },
  danger: { dot: "bg-danger", text: "text-danger", bg: "bg-danger-soft" },
  accent: { dot: "bg-accent", text: "text-accent-bright", bg: "bg-accent-soft" },
  neutral: { dot: "bg-ink-500", text: "text-ink-400", bg: "bg-base-700" },
};

interface StatusBadgeProps {
  label: string;
  tone?: Tone;
  pulse?: boolean;
  className?: string;
}

export function StatusBadge({ label, tone = "neutral", pulse = false, className }: StatusBadgeProps) {
  const styles = TONE_STYLES[tone];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium",
        styles.bg,
        styles.text,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", styles.dot, pulse && "animate-pulse-dot")} />
      {label}
    </span>
  );
}
