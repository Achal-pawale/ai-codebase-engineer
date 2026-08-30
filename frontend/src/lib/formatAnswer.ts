function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Light formatting for Gemini's free-text answers: inline `code` spans and
 * the "(file.py, lines 10-15)" citation pattern the /ask and /investigate
 * prompts explicitly ask the model to use get a subtle highlight. Everything
 * else stays as escaped plain text — this is not a markdown renderer.
 */
export function formatAnswerHtml(text: string): string {
  let html = escapeHtml(text);

  html = html.replace(
    /`([^`]+)`/g,
    '<code class="rounded bg-base-700 px-1 py-0.5 font-mono text-[12px] text-accent-bright">$1</code>'
  );

  html = html.replace(
    /\(([\w\-./]+\.\w+),\s*lines?\s*\d+(?:[-–]\d+)?\)/gi,
    '<span class="rounded bg-accent-soft px-1 py-0.5 font-mono text-[11px] text-accent-bright">$&</span>'
  );

  return html;
}
