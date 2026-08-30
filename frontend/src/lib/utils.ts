export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** "owner/repo" from a GitHub URL, falling back to the last path segment. */
export function repoLabelFromUrl(url: string): string {
  const cleaned = url.trim().replace(/\.git$/, "").replace(/\/+$/, "");
  const parts = cleaned.split("/").filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
  }

  return parts[parts.length - 1] || url;
}

export function isLikelyGithubUrl(value: string): boolean {
  return /^https?:\/\/(www\.)?github\.com\/[^/\s]+\/[^/\s]+\/?$/i.test(value.trim());
}

/** Human label for a file extension, e.g. ".py" -> "Python". */
const LANGUAGE_NAMES: Record<string, string> = {
  ".py": "Python",
  ".js": "JavaScript",
  ".ts": "TypeScript",
  ".jsx": "JSX",
  ".tsx": "TSX",
  ".java": "Java",
  ".go": "Go",
  ".rb": "Ruby",
  ".php": "PHP",
  ".c": "C",
  ".cpp": "C++",
  ".cs": "C#",
};

export function languageNameFor(extension: string): string {
  return LANGUAGE_NAMES[extension] ?? extension.replace(".", "").toUpperCase();
}

export function truncateMiddle(value: string, max = 56): string {
  if (value.length <= max) return value;
  const keep = Math.floor((max - 1) / 2);
  return `${value.slice(0, keep)}…${value.slice(value.length - keep)}`;
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
