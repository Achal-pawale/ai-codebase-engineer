import type { AnalyzeSuccess, ChunkSuccess } from "@/types/api";

/**
 * Everything here is computed client-side from fields the backend actually
 * returns (chunk types, import lists, file paths) — no numbers are invented.
 */

export interface StructureCounts {
  functions: number;
  classes: number;
}

export function countStructures(chunk: ChunkSuccess | null): StructureCounts {
  if (!chunk) return { functions: 0, classes: 0 };

  let functions = 0;
  let classes = 0;

  for (const c of chunk.chunks) {
    if (c.type === "class") classes += 1;
    else functions += 1; // function | async_function
  }

  return { functions, classes };
}

export function countUniqueImports(chunk: ChunkSuccess | null): number {
  if (!chunk) return 0;
  const set = new Set<string>();
  for (const c of chunk.chunks) {
    for (const imp of c.imports) set.add(imp);
  }
  return set.size;
}

/** Heuristic only — the backend doesn't return a test-file count, so this reads file paths already returned by /analyze. */
export function estimateTestFileCount(analyze: AnalyzeSuccess | null): number {
  if (!analyze) return 0;
  return analyze.files.filter((f) => {
    const lower = f.path.toLowerCase();
    return lower.includes("test_") || lower.includes("_test") || lower.includes("/tests/") || lower.startsWith("tests/");
  }).length;
}

export interface FileTreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: FileTreeNode[];
}

export function buildFileTree(paths: string[]): FileTreeNode[] {
  const root: FileTreeNode[] = [];

  for (const fullPath of paths) {
    const segments = fullPath.split("/").filter(Boolean);
    let level = root;
    let accPath = "";

    segments.forEach((segment, idx) => {
      accPath = accPath ? `${accPath}/${segment}` : segment;
      const isDir = idx < segments.length - 1;
      let node = level.find((n) => n.name === segment && n.isDir === isDir);

      if (!node) {
        node = { name: segment, path: accPath, isDir, children: [] };
        level.push(node);
      }

      level = node.children;
    });
  }

  const sortTree = (nodes: FileTreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((n) => sortTree(n.children));
  };

  sortTree(root);
  return root;
}
