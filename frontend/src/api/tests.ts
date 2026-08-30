import { apiClient } from "./client";
import type { DetectTestsResponse, ValidateResponse } from "@/types/api";

/** POST /detect-tests — sniffs the repo for a known test framework/config. */
export function detectTests(repoPath: string): Promise<DetectTestsResponse> {
  return apiClient.post("/detect-tests", { repo_path: repoPath }, { timeoutMs: 15_000 });
}

/** POST /validate — actually runs the detected test command (up to 300s server-side). */
export function validateRepository(repoPath: string): Promise<ValidateResponse> {
  return apiClient.post("/validate", { repo_path: repoPath }, { timeoutMs: 310_000 });
}
