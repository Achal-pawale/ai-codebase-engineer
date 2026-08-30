import React, { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from "react";
import { analyzeRepository, chunkRepository, ingestRepository } from "@/api/repository";
import type { AnalyzeSuccess, ChunkSuccess, IngestSuccess } from "@/types/api";
import { ApiError } from "@/types/api";
import { isLikelyGithubUrl, repoLabelFromUrl } from "@/lib/utils";

export type ConnectionStage = "connecting" | "cloning" | "analyzing" | "indexing" | "ready";

export type ConnectionStatus = "idle" | "working" | "ready" | "error";

interface RepositoryState {
  status: ConnectionStatus;
  stage: ConnectionStage | null;
  repoUrl: string | null;
  repoLabel: string | null;
  repoPath: string | null;
  ingest: IngestSuccess | null;
  analyze: AnalyzeSuccess | null;
  chunk: ChunkSuccess | null;
  error: string | null;
}

type Action =
  | { type: "START"; repoUrl: string }
  | { type: "STAGE"; stage: ConnectionStage }
  | { type: "INGEST_OK"; result: IngestSuccess }
  | { type: "ANALYZE_OK"; result: AnalyzeSuccess }
  | { type: "CHUNK_OK"; result: ChunkSuccess }
  | { type: "ERROR"; message: string }
  | { type: "RESET" }
  | { type: "HYDRATE"; state: RepositoryState };

const STORAGE_KEY = "ace:connected-repo";

const initialState: RepositoryState = {
  status: "idle",
  stage: null,
  repoUrl: null,
  repoLabel: null,
  repoPath: null,
  ingest: null,
  analyze: null,
  chunk: null,
  error: null,
};

function reducer(state: RepositoryState, action: Action): RepositoryState {
  switch (action.type) {
    case "START":
      return {
        ...initialState,
        status: "working",
        stage: "connecting",
        repoUrl: action.repoUrl,
        repoLabel: repoLabelFromUrl(action.repoUrl),
      };
    case "STAGE":
      return { ...state, stage: action.stage };
    case "INGEST_OK":
      return { ...state, ingest: action.result, repoPath: action.result.cloned_to, stage: "analyzing" };
    case "ANALYZE_OK":
      return { ...state, analyze: action.result, stage: "indexing" };
    case "CHUNK_OK":
      return { ...state, chunk: action.result, stage: "ready", status: "ready" };
    case "ERROR":
      return { ...state, status: "error", error: action.message };
    case "RESET":
      return initialState;
    case "HYDRATE":
      return action.state;
    default:
      return state;
  }
}

interface RepositoryContextValue extends RepositoryState {
  connect: (repoUrl: string) => Promise<void>;
  reset: () => void;
  isReady: boolean;
}

const RepositoryContext = createContext<RepositoryContextValue | null>(null);

export function RepositoryProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    try {
      const parsed = JSON.parse(raw) as RepositoryState;
      if (parsed.status === "ready" && parsed.repoPath) {
        dispatch({ type: "HYDRATE", state: parsed });
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (state.status === "ready") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else if (state.status === "idle") {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [state]);

  const connect = useCallback(async (repoUrl: string) => {
    if (!isLikelyGithubUrl(repoUrl)) {
      dispatch({ type: "ERROR", message: "That doesn't look like a GitHub repository URL. Expected format: https://github.com/user/repository" });
      return;
    }

    dispatch({ type: "START", repoUrl });

    try {
      dispatch({ type: "STAGE", stage: "cloning" });
      const ingestResult = await ingestRepository(repoUrl);

      if (!ingestResult.success) {
        dispatch({ type: "ERROR", message: ingestResult.error || "Cloning the repository failed." });
        return;
      }

      dispatch({ type: "INGEST_OK", result: ingestResult });

      const analyzeResult = await analyzeRepository(ingestResult.cloned_to);

      if (!analyzeResult.success) {
        dispatch({ type: "ERROR", message: analyzeResult.error || "Analyzing the repository failed." });
        return;
      }

      dispatch({ type: "ANALYZE_OK", result: analyzeResult });

      const chunkResult = await chunkRepository(ingestResult.cloned_to);

      if (!chunkResult.success) {
        dispatch({ type: "ERROR", message: chunkResult.error || "Indexing the repository failed." });
        return;
      }

      dispatch({ type: "CHUNK_OK", result: chunkResult });
    } catch (error) {
      if (error instanceof ApiError) {
        dispatch({ type: "ERROR", message: error.message });
      } else {
        dispatch({ type: "ERROR", message: "Something unexpected went wrong while connecting the repository." });
      }
    }
  }, []);

  const reset = useCallback(() => dispatch({ type: "RESET" }), []);

  const value = useMemo<RepositoryContextValue>(
    () => ({ ...state, connect, reset, isReady: state.status === "ready" && !!state.repoPath }),
    [state, connect, reset]
  );

  return <RepositoryContext.Provider value={value}>{children}</RepositoryContext.Provider>;
}

export function useRepository(): RepositoryContextValue {
  const ctx = useContext(RepositoryContext);
  if (!ctx) throw new Error("useRepository must be used within RepositoryProvider");
  return ctx;
}
