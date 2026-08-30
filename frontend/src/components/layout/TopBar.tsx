import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Github, LogOut, Menu } from "lucide-react";
import { Logo } from "./Logo";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useBackendStatus } from "@/hooks/useBackendStatus";
import { useRepository } from "@/state/RepositoryContext";
import { truncateMiddle } from "@/lib/utils";

const BACKEND_LABEL: Record<ReturnType<typeof useBackendStatus>, string> = {
  checking: "Checking backend…",
  online: "Backend online",
  offline: "Backend unreachable",
};

interface TopBarProps {
  onToggleSidebar?: () => void;
}

export function TopBar({ onToggleSidebar }: TopBarProps) {
  const backendStatus = useBackendStatus();
  const { repoUrl, repoLabel, reset } = useRepository();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleDisconnect = () => {
    setMenuOpen(false);
    reset();
    navigate("/");
  };

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-base-600 bg-base-850 px-3">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="flex h-7 w-7 items-center justify-center rounded text-ink-400 hover:bg-base-700 hover:text-ink-100 lg:hidden"
        >
          <Menu size={16} />
        </button>

        <div className="flex items-center gap-2">
          <Logo />
          <span className="hidden text-sm font-semibold text-ink-100 sm:inline">AI Codebase Engineer</span>
        </div>

        {repoLabel && (
          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="flex items-center gap-1.5 rounded-md border border-base-600 bg-base-800 px-2.5 py-1 text-xs text-ink-300 transition-colors hover:border-base-500 hover:text-ink-100"
            >
              <Github size={12} />
              <span className="max-w-[160px] truncate font-mono sm:max-w-[240px]">{repoLabel}</span>
              <ChevronDown size={12} className="text-ink-500" />
            </button>

            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                <div className="absolute left-0 top-full z-20 mt-1 w-64 rounded-md border border-base-600 bg-base-800 py-1 shadow-panel animate-fade-in">
                  <div className="border-b border-base-700 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-wide text-ink-500">Connected repository</p>
                    <p className="mt-0.5 truncate font-mono text-xs text-ink-300" title={repoUrl ?? undefined}>
                      {truncateMiddle(repoUrl ?? "", 40)}
                    </p>
                  </div>
                  <button
                    onClick={handleDisconnect}
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs text-danger transition-colors hover:bg-danger-soft"
                  >
                    <LogOut size={12} />
                    Disconnect repository
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <StatusBadge
        label={BACKEND_LABEL[backendStatus]}
        tone={backendStatus === "online" ? "ok" : backendStatus === "checking" ? "neutral" : "danger"}
        pulse={backendStatus === "checking"}
      />
    </header>
  );
}
