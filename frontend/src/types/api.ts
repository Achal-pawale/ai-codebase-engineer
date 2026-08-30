/**
 * Types mirror the ACTUAL request/response shapes returned by the FastAPI
 * backend (backend/app/main.py + backend/app/services.py). Nothing here
 * represents an endpoint or field that doesn't exist server-side.
 */

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

export type ChunkType = "function" | "async_function" | "class";

export interface CodeChunk {
  chunk_id: number;
  type: ChunkType;
  name: string;
  file: string;
  language: string;
  imports: string[];
  references: string[];
  start_line: number;
  end_line: number;
  content: string;
}

export interface ScoredChunk {
  score: number;
  matched_words: string[];
  chunk: CodeChunk;
}

// ---------------------------------------------------------------------------
// POST /ingest
// ---------------------------------------------------------------------------

export interface IngestSuccess {
  success: true;
  cloned_to: string;
  top_level_items: string[];
  file_count: number;
}

export interface IngestFailure {
  success: false;
  error: string;
}

export type IngestResponse = IngestSuccess | IngestFailure;

// ---------------------------------------------------------------------------
// POST /analyze
// ---------------------------------------------------------------------------

export interface AnalyzedFile {
  path: string;
  extension: string;
  size_bytes: number;
}

export interface AnalyzeSuccess {
  success: true;
  summary: {
    total_code_files: number;
    language_counts: Record<string, number>;
    directory_count: number;
    important_files: string[];
  };
  directories: string[];
  files: AnalyzedFile[];
}

export interface AnalyzeFailure {
  success: false;
  error: string;
}

export type AnalyzeResponse = AnalyzeSuccess | AnalyzeFailure;

// ---------------------------------------------------------------------------
// POST /chunk
// ---------------------------------------------------------------------------

export interface ChunkSuccess {
  success: true;
  repository: string;
  files_processed: number;
  files_skipped: number;
  total_chunks: number;
  chunks_file: string;
  chunks: CodeChunk[];
}

export interface ChunkFailure {
  success: false;
  error: string;
}

export type ChunkResponse = ChunkSuccess | ChunkFailure;

// ---------------------------------------------------------------------------
// POST /retrieve
// ---------------------------------------------------------------------------

export interface RetrieveResponse {
  success: true;
  query: string;
  match_count: number;
  results: ScoredChunk[];
}

// ---------------------------------------------------------------------------
// POST /context
// ---------------------------------------------------------------------------

export interface ContextResponse {
  success: true;
  query: string;
  chunk_count: number;
  context: string;
}

// ---------------------------------------------------------------------------
// POST /ask
// ---------------------------------------------------------------------------

export interface AskResponse {
  success: true;
  question: string;
  answer: string;
  retrieved_chunks: number;
  model: string;
  sources: string[];
}

// ---------------------------------------------------------------------------
// POST /relationships
// ---------------------------------------------------------------------------

export interface RelationshipLocation {
  file: string;
  type: string;
  start_line: number;
  end_line: number;
}

export interface UsedByEntry extends RelationshipLocation {
  name: string;
}

export interface RelationshipsResponse {
  success: true;
  name: string;
  defined_at: RelationshipLocation[];
  depends_on: string[];
  used_by: UsedByEntry[];
  imported_in_files: string[];
}

// ---------------------------------------------------------------------------
// POST /investigate
// ---------------------------------------------------------------------------

export interface InvestigateResponse {
  success: true;
  bug_description: string;
  investigation: string;
  retrieved_chunks: number;
  related_symbols: string[];
  sources: string[];
  model?: string;
}

// ---------------------------------------------------------------------------
// POST /plan
// ---------------------------------------------------------------------------

export interface PlanResponse {
  success: true;
  feature_request: string;
  plan: string;
  retrieved_chunks: number;
  related_symbols: string[];
  sources: string[];
  model?: string;
}

// ---------------------------------------------------------------------------
// POST /propose-change
// ---------------------------------------------------------------------------

export interface ProposeChangeSuccess {
  success: true;
  file_path: string;
  instruction: string;
  changed: boolean;
  diff: string;
  message?: string;
  proposed_file_saved_to?: string;
  model?: string;
}

export interface ProposeChangeFailure {
  success: false;
  error: string;
}

export type ProposeChangeResponse = ProposeChangeSuccess | ProposeChangeFailure;

// ---------------------------------------------------------------------------
// POST /detect-tests
// ---------------------------------------------------------------------------

export interface DetectTestsResponse {
  success: true;
  repository: string;
  detected: boolean;
  framework: string | null;
  command: string | null;
}

// ---------------------------------------------------------------------------
// POST /validate
// ---------------------------------------------------------------------------

export interface ValidateResultRan {
  success: true;
  validated: true;
  passed: boolean;
  framework: string;
  command: string;
  return_code: number;
  stdout: string;
  stderr: string;
  repository: string;
}

export interface ValidateResultNoFramework {
  success: true;
  validated: false;
  passed: false;
  message: string;
  repository: string;
}

export interface ValidateResultTimeoutOrError {
  success: false;
  validated: true;
  passed: false;
  error: string;
  repository: string;
}

export type ValidateResponse =
  | ValidateResultRan
  | ValidateResultNoFramework
  | ValidateResultTimeoutOrError;

// ---------------------------------------------------------------------------
// POST /engineer — combined ingest+chunk+task workflow.
// Not used by the primary UI flow (screens need the granular endpoints so a
// repo isn't re-cloned on every question), included for completeness only.
// ---------------------------------------------------------------------------

export type EngineerTaskType = "ask" | "investigate" | "plan";

export interface EngineerResponse {
  success: boolean;
  stage?: string;
  error?: string;
  workflow?: string[];
  repository?: { url: string; path: string };
  ingest?: Record<string, unknown>;
  chunk?: Record<string, unknown>;
  task?: { type: EngineerTaskType; question: string; top_k: number };
  result?: AskResponse | InvestigateResponse | PlanResponse;
}

// ---------------------------------------------------------------------------
// Client-side error envelope (not a backend shape — thrown by src/api/client.ts)
// ---------------------------------------------------------------------------

export type ApiErrorKind = "network" | "timeout" | "http" | "validation" | "rate_limit";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  detail?: unknown;

  constructor(kind: ApiErrorKind, message: string, status?: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}
