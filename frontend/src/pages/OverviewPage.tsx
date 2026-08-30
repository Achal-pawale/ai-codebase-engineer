import { useNavigate } from "react-router-dom";
import { Bug, ClipboardList, Files, FolderTree, GitBranch, Github, History, Layers, MessageSquareText, Package, TestTube2 } from "lucide-react";
import { useRepository } from "@/state/RepositoryContext";
import { StatCard } from "@/components/ui/StatCard";
import { QuickAction } from "@/components/ui/QuickAction";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { FileTree } from "@/components/FileTree";
import { buildFileTree, countStructures, countUniqueImports, estimateTestFileCount } from "@/lib/deriveStats";
import { languageNameFor } from "@/lib/utils";

export function OverviewPage() {
  const { repoUrl, repoLabel, ingest, analyze, chunk } = useRepository();
  const navigate = useNavigate();

  const structures = countStructures(chunk);
  const uniqueImports = countUniqueImports(chunk);
  const testFileEstimate = estimateTestFileCount(analyze);
  const tree = analyze ? buildFileTree(analyze.files.map((f) => f.path)) : [];

  const languages = analyze
    ? Object.entries(analyze.summary.language_counts).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className="mx-auto max-w-6xl px-5 py-6">
      {/* Repository header */}
      <div className="rounded-lg border border-base-600 bg-base-850 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Github size={16} className="text-ink-400" />
              <h1 className="truncate text-base font-semibold text-ink-100">{repoLabel}</h1>
            </div>
            <a
              href={repoUrl ?? "#"}
              target="_blank"
              rel="noreferrer"
              className="mt-1 block truncate font-mono text-xs text-ink-500 hover:text-accent-bright"
            >
              {repoUrl}
            </a>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <StatusBadge label="Cloned" tone="ok" />
            <StatusBadge label="Analyzed" tone="ok" />
            <StatusBadge label={`Indexed · ${chunk?.total_chunks ?? 0} chunks`} tone="ok" />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-base-700 pt-4 text-xs text-ink-500">
          <div className="flex items-center gap-1.5">
            <GitBranch size={13} />
            <span className="text-ink-600">Branch not reported by backend</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Layers size={13} />
            {languages.length === 0 && <span className="text-ink-600">No recognized languages</span>}
            {languages.map(([ext, count]) => (
              <span key={ext} className="rounded bg-base-700 px-1.5 py-0.5 font-mono text-[11px] text-ink-300">
                {languageNameFor(ext)} · {count}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard icon={Files} label="Code files" value={analyze?.summary.total_code_files ?? 0} sublabel={`${ingest?.file_count ?? 0} files total`} />
        <StatCard icon={Package} label="Functions" value={structures.functions} />
        <StatCard icon={Layers} label="Classes" value={structures.classes} />
        <StatCard icon={FolderTree} label="Chunks" value={chunk?.total_chunks ?? 0} />
        <StatCard icon={TestTube2} label="Test files" value={testFileEstimate} sublabel="by filename pattern" />
        <StatCard icon={Package} label="Unique imports" value={uniqueImports} />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Quick actions */}
        <div className="flex flex-col gap-3 lg:col-span-1">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Quick actions</p>
          <QuickAction
            icon={MessageSquareText}
            title="Ask Codebase"
            description="Ask a grounded question and get an answer with file citations."
            onClick={() => navigate("/ask")}
          />
          <QuickAction
            icon={Bug}
            title="Investigate Issue"
            description="Describe a bug and get a suspected cause with evidence."
            onClick={() => navigate("/investigate")}
          />
          <QuickAction
            icon={ClipboardList}
            title="Plan a Change"
            description="Describe a feature and get an implementation plan."
            onClick={() => navigate("/plan")}
          />

          <div className="mt-2 rounded-lg border border-base-600 bg-base-850 p-4">
            <div className="flex items-center gap-2 text-ink-500">
              <History size={14} />
              <span className="text-xs font-medium uppercase tracking-wide">Recent activity</span>
            </div>
            <EmptyState
              icon={History}
              title="Not tracked yet"
              description="The backend doesn't persist a history of questions or changes across sessions."
              className="mt-2 border-none py-6"
            />
          </div>
        </div>

        {/* File structure */}
        <div className="rounded-lg border border-base-600 bg-base-850 lg:col-span-2">
          <div className="flex items-center gap-2 border-b border-base-600 px-4 py-2.5 text-ink-500">
            <FolderTree size={14} />
            <span className="text-xs font-medium uppercase tracking-wide">Repository structure</span>
            <span className="ml-auto font-mono text-[11px] text-ink-600">{analyze?.files.length ?? 0} files</span>
          </div>
          <div className="max-h-[420px] overflow-auto scrollbar-thin px-3 py-2">
            <FileTree nodes={tree} />
          </div>
        </div>
      </div>
    </div>
  );
}
