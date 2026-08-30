/**
 * The /investigate and /plan prompts (backend/app/services.py) instruct
 * Gemini to reply using a fixed set of ALL-CAPS section headers. This parser
 * splits on those headers defensively — if the model didn't follow the
 * format exactly, everything falls back into a single "Response" section
 * rather than silently dropping text.
 */
export interface ParsedSection {
  heading: string;
  body: string;
}

export function parseHeadedSections(raw: string, headers: string[]): ParsedSection[] {
  if (!raw || !raw.trim()) return [];

  const pattern = new RegExp(`^(${headers.map((h) => h.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")}):?\\s*$`, "gim");

  const matches = [...raw.matchAll(pattern)];

  if (matches.length === 0) {
    return [{ heading: "Response", body: raw.trim() }];
  }

  const sections: ParsedSection[] = [];

  for (let i = 0; i < matches.length; i += 1) {
    const current = matches[i];
    const next = matches[i + 1];

    const start = (current.index ?? 0) + current[0].length;
    const end = next ? next.index ?? raw.length : raw.length;

    const body = raw.slice(start, end).trim();
    const heading = current[1];

    if (body) sections.push({ heading, body });
  }

  return sections;
}

export const INVESTIGATE_HEADERS = [
  "SUSPECTED CAUSE",
  "EVIDENCE",
  "FILES TO CHECK NEXT",
  "CONFIDENCE",
];

export const PLAN_HEADERS = ["AFFECTED FILES", "PROPOSED CHANGES", "RISKS", "TESTS TO CONSIDER"];

export function extractConfidence(sections: ParsedSection[]): "High" | "Medium" | "Low" | null {
  const section = sections.find((s) => s.heading.toUpperCase() === "CONFIDENCE");
  if (!section) return null;

  const text = section.body.toLowerCase();
  if (text.includes("high")) return "High";
  if (text.includes("medium")) return "Medium";
  if (text.includes("low")) return "Low";
  return null;
}
