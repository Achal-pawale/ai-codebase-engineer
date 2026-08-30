import { apiClient, AI_TIMEOUT_MS } from "./client";
import type { PlanResponse } from "@/types/api";

/** POST /plan — Gemini implementation plan over the retrieved chunks. */
export function planFeature(repoPath: string, featureRequest: string, topK = 5): Promise<PlanResponse> {
  return apiClient.post(
    "/plan",
    { repo_path: repoPath, feature_request: featureRequest, top_k: topK },
    { timeoutMs: AI_TIMEOUT_MS }
  );
}
