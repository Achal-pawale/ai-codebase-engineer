import { apiClient, AI_TIMEOUT_MS } from "./client";
import type { ProposeChangeResponse } from "@/types/api";

/**
 * POST /propose-change — generates a full rewritten file from an instruction
 * and returns a unified diff. The backend persists the proposed file under
 * backend/proposed_changes/ whenever changed is true; there is currently no
 * approve/apply or reject/discard endpoint (see ProposedChangesPage).
 */
export function proposeChange(
  repoPath: string,
  filePath: string,
  instruction: string
): Promise<ProposeChangeResponse> {
  return apiClient.post(
    "/propose-change",
    { repo_path: repoPath, file_path: filePath, instruction },
    { timeoutMs: AI_TIMEOUT_MS }
  );
}
