import { apiClient } from "./client";
import type {
  AnalyzeResponse,
  ChunkResponse,
  IngestResponse,
  RelationshipsResponse,
  RetrieveResponse,
  ContextResponse,
} from "@/types/api";

/** GET / — lightweight liveness probe used for the backend status dot. */
export function checkBackendHealth(): Promise<{ status: string }> {
  return apiClient.get("/health", { timeoutMs: 5_000 });
}

/** POST /ingest — clones the repo (shallow) into the backend's workspace dir. */
export function ingestRepository(repoUrl: string): Promise<IngestResponse> {
  return apiClient.post("/ingest", { repo_url: repoUrl }, { timeoutMs: 600_000 });  // was 60_000
}

export function analyzeRepository(clonedTo: string): Promise<AnalyzeResponse> {
  return apiClient.post("/analyze", { cloned_to: clonedTo }, { timeoutMs: 60_000 });  // was 30_000
}

export function chunkRepository(repoPath: string): Promise<ChunkResponse> {
  return apiClient.post("/chunk", { repo_path: repoPath }, { timeoutMs: 120_000 });  // was 60_000
}

/** POST /retrieve — keyword-scored chunk search; the source of "evidence" shown in Ask/Investigate/Plan. */
export function retrieveChunks(repoPath: string, query: string, topK = 5): Promise<RetrieveResponse> {
  return apiClient.post("/retrieve", { repo_path: repoPath, query, top_k: topK });
}

/** POST /context — same retrieval, pre-formatted into a single context string. Exposed for completeness; not wired into a screen. */
export function buildContext(repoPath: string, query: string, topK = 5): Promise<ContextResponse> {
  return apiClient.post("/context", { repo_path: repoPath, query, top_k: topK });
}

/** POST /relationships — depends-on / used-by graph for a single named symbol. */
export function getRelationships(repoPath: string, name: string): Promise<RelationshipsResponse> {
  return apiClient.post("/relationships", { repo_path: repoPath, name });
}
