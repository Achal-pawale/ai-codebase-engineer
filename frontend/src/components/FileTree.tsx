import { useState } from "react";
import { ChevronRight, File, Folder } from "lucide-react";
import type { FileTreeNode } from "@/lib/deriveStats";
import { cn } from "@/lib/utils";

interface FileTreeProps {
  nodes: FileTreeNode[];
  depth?: number;
  defaultOpen?: boolean;
}

function TreeNode({ node, depth, defaultOpen }: { node: FileTreeNode; depth: number; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen && depth < 1);

  if (!node.isDir) {
    return (
      <div className="flex items-center gap-1.5 py-0.5 text-xs text-ink-400" style={{ paddingLeft: depth * 14 + 20 }}>
        <File size={12} className="shrink-0 text-ink-600" />
        <span className="truncate font-mono">{node.name}</span>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1 py-0.5 text-left text-xs text-ink-300 hover:text-ink-100"
        style={{ paddingLeft: depth * 14 }}
      >
        <ChevronRight size={12} className={cn("shrink-0 text-ink-600 transition-transform", open && "rotate-90")} />
        <Folder size={12} className="shrink-0 text-accent-bright" />
        <span className="truncate font-mono">{node.name}</span>
      </button>
      {open && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.path + child.isDir} node={child} depth={depth + 1} defaultOpen={defaultOpen} />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({ nodes, depth = 0, defaultOpen = true }: FileTreeProps) {
  if (nodes.length === 0) {
    return <p className="px-2 py-3 text-xs text-ink-500">No files to show.</p>;
  }

  return (
    <div>
      {nodes.map((node) => (
        <TreeNode key={node.path + node.isDir} node={node} depth={depth} defaultOpen={defaultOpen} />
      ))}
    </div>
  );
}
