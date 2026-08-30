/**
 * Minimal regex-based syntax coloring — not a real tokenizer/lexer.
 * Good enough for a read-only evidence viewer; intentionally not a full
 * editor/IDE experience (per the product brief).
 */

const KEYWORDS: Record<string, string[]> = {
  python: [
    "def", "class", "return", "if", "elif", "else", "for", "while", "try", "except",
    "finally", "import", "from", "as", "with", "pass", "break", "continue", "lambda",
    "yield", "raise", "in", "is", "not", "and", "or", "None", "True", "False", "self",
    "async", "await", "global", "nonlocal", "assert", "del",
  ],
  javascript: [
    "const", "let", "var", "function", "return", "if", "else", "for", "while", "try",
    "catch", "finally", "import", "export", "from", "as", "class", "extends", "new",
    "this", "async", "await", "yield", "typeof", "instanceof", "in", "of", "null",
    "undefined", "true", "false", "switch", "case", "break", "continue", "default",
    "throw", "static",
  ],
  typescript: [], // filled below
  tsx: [],
  jsx: [],
  java: ["public", "private", "protected", "class", "static", "void", "return", "if", "else", "for", "while", "new", "import", "package", "extends", "implements", "try", "catch", "finally", "throw", "final", "interface"],
  go: ["func", "package", "import", "return", "if", "else", "for", "range", "var", "const", "type", "struct", "interface", "go", "defer", "chan", "select", "case", "switch", "nil", "true", "false"],
  generic: ["function", "return", "if", "else", "for", "while", "class", "import", "export", "const", "let", "var", "new", "try", "catch"],
};

KEYWORDS.typescript = [...KEYWORDS.javascript, "interface", "type", "implements", "readonly", "enum", "namespace", "public", "private", "protected"];
KEYWORDS.tsx = KEYWORDS.typescript;
KEYWORDS.jsx = KEYWORDS.javascript;

export function languageForExtension(extension: string): string {
  const map: Record<string, string> = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
  };
  return map[extension.toLowerCase()] ?? "generic";
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function highlightLine(line: string, language: string): string {
  const escaped = escapeHtml(line);
  const keywords = KEYWORDS[language] ?? KEYWORDS.generic;

  // Order matters: comments/strings first so we don't re-color inside them.
  const commentPattern = language === "python" ? /(#.*$)/ : /(\/\/.*$)/;

  const parts: string[] = [];
  const commentMatch = escaped.match(commentPattern);
  const codePart = commentMatch ? escaped.slice(0, commentMatch.index) : escaped;
  const commentPart = commentMatch ? escaped.slice(commentMatch.index) : "";

  let working = codePart;

  working = working.replace(/(&quot;.*?&quot;|&#39;.*?&#39;|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, (m) => `<span class="tok-str">${m}</span>`);
  working = working.replace(/\b(\d+\.?\d*)\b/g, '<span class="tok-num">$1</span>');

  if (keywords.length > 0) {
    const kwPattern = new RegExp(`\\b(${keywords.join("|")})\\b`, "g");
    working = working.replace(kwPattern, '<span class="tok-kw">$1</span>');
  }

  working = working.replace(/\b([A-Za-z_][A-Za-z0-9_]*)(?=\()/g, '<span class="tok-fn">$1</span>');

  parts.push(working);
  if (commentPart) parts.push(`<span class="tok-comment">${commentPart}</span>`);

  return parts.join("");
}
