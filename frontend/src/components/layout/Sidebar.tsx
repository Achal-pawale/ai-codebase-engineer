import { NavLink } from "react-router-dom";
import { LayoutGrid, MessageSquareText, Bug, ClipboardList, GitPullRequest, FlaskConical, X } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/overview", label: "Overview", icon: LayoutGrid },
  { to: "/ask", label: "Ask Codebase", icon: MessageSquareText },
  { to: "/investigate", label: "Investigate", icon: Bug },
  { to: "/plan", label: "Plan Changes", icon: ClipboardList },
  { to: "/changes", label: "Changes", icon: GitPullRequest },
  { to: "/tests", label: "Tests", icon: FlaskConical },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {open && <div className="fixed inset-0 z-20 bg-black/50 lg:hidden" onClick={onClose} />}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-56 shrink-0 border-r border-base-600 bg-base-850 transition-transform lg:static lg:z-auto lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-12 items-center justify-between border-b border-base-600 px-3 lg:hidden">
          <span className="text-sm font-medium text-ink-200">Navigation</span>
          <button onClick={onClose} className="flex h-7 w-7 items-center justify-center rounded text-ink-400 hover:bg-base-700">
            <X size={15} />
          </button>
        </div>

        <nav className="flex flex-col gap-0.5 p-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md border-l-2 px-2.5 py-2 text-sm transition-colors",
                  isActive
                    ? "border-accent bg-accent-soft text-ink-100"
                    : "border-transparent text-ink-400 hover:bg-base-800 hover:text-ink-100"
                )
              }
            >
              <Icon size={15} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
