import { apiClient, AI_TIMEOUT_MS } from "./client";
import type { InvestigateResponse } from "@/types/api";

/** POST /investigate — Gemini bug investigation over the retrieved chunks. */
export function investigateBug(
  repoPath: string,
  bugDescription: string,
  topK = 5
): Promise<InvestigateResponse> {
  return apiClient.post(
    "/investigate",
    { repo_path: repoPath, bug_description: bugDescription, top_k: topK },
    { timeoutMs: AI_TIMEOUT_MS }
  );
}
