import { apiClient, AI_TIMEOUT_MS } from "./client";
import type { AskResponse } from "@/types/api";

/** POST /ask — Gemini-grounded Q&A over the retrieved chunks. */
export function askCodebase(repoPath: string, question: string, topK = 5): Promise<AskResponse> {
  return apiClient.post("/ask", { repo_path: repoPath, question, top_k: topK }, { timeoutMs: AI_TIMEOUT_MS });
}
