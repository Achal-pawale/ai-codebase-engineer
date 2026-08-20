from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import services


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI Codebase Engineer"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class IngestRequest(BaseModel):
    repo_url: str


class AnalyzeRequest(BaseModel):
    cloned_to: str


class ChunkRequest(BaseModel):
    repo_path: str


class RetrieveRequest(BaseModel):
    repo_path: str
    query: str
    top_k: int = 5


class PromptRequest(BaseModel):
    repo_path: str
    question: str
    top_k: int = 5


class AskRequest(BaseModel):
    repo_path: str
    question: str
    top_k: int = 5


class RelationshipsRequest(BaseModel):
    repo_path: str
    name: str


class InvestigateRequest(BaseModel):
    repo_path: str
    bug_description: str
    top_k: int = 5


class PlanRequest(BaseModel):
    repo_path: str
    feature_request: str
    top_k: int = 5


class ProposeChangeRequest(BaseModel):
    repo_path: str
    file_path: str
    instruction: str


class DetectTestsRequest(BaseModel):
    repo_path: str


class ValidateRequest(BaseModel):
    repo_path: str


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():

    return {
        "message": "AI Codebase Engineer API is running."
    }


@app.get("/health")
def health_check():

    return {
        "status": "ok"
    }


# ============================================================
# INGEST
# ============================================================

@app.post("/ingest")
def ingest_repo(req: IngestRequest):

    return services.ingest_repo(
        req.repo_url
    )


# ============================================================
# ANALYZE
# ============================================================

@app.post("/analyze")
def analyze_repo(req: AnalyzeRequest):

    return services.analyze_repo(
        Path(req.cloned_to)
    )


# ============================================================
# CHUNK
# ============================================================

@app.post("/chunk")
def chunk_repo(req: ChunkRequest):

    return services.chunk_repo(
        Path(req.repo_path)
    )


# ============================================================
# RETRIEVE
# ============================================================

@app.post("/retrieve")
def retrieve_chunks(req: RetrieveRequest):

    return services.retrieve_chunks(
        Path(req.repo_path),
        req.query,
        req.top_k
    )


# ============================================================
# CONTEXT
# ============================================================

@app.post("/context")
def build_context(req: RetrieveRequest):

    return services.build_context(
        Path(req.repo_path),
        req.query,
        req.top_k
    )


# ============================================================
# PROMPT
# ============================================================

@app.post("/prompt")
def build_prompt(req: PromptRequest):

    return services.build_prompt(
        Path(req.repo_path),
        req.question,
        req.top_k
    )


# ============================================================
# ASK
# ============================================================

@app.post("/ask")
def ask_codebase(req: AskRequest):

    return services.ask_codebase(
        Path(req.repo_path),
        req.question,
        req.top_k
    )


# ============================================================
# RELATIONSHIPS
# ============================================================

@app.post("/relationships")
def get_relationships(
    req: RelationshipsRequest
):

    return services.get_relationships(
        Path(req.repo_path),
        req.name
    )


# ============================================================
# INVESTIGATE
# ============================================================

@app.post("/investigate")
def investigate_bug(
    req: InvestigateRequest
):

    return services.investigate_bug(
        Path(req.repo_path),
        req.bug_description,
        req.top_k
    )


# ============================================================
# PLAN
# ============================================================

@app.post("/plan")
def plan_feature(
    req: PlanRequest
):

    return services.plan_feature(
        Path(req.repo_path),
        req.feature_request,
        req.top_k
    )


# ============================================================
# PROPOSE CHANGE
# ============================================================

@app.post("/propose-change")
def propose_change(
    req: ProposeChangeRequest
):

    return services.propose_change(
        Path(req.repo_path),
        req.file_path,
        req.instruction
    )


# ============================================================
# DAY 12 — TEST DETECTION
# ============================================================

@app.post("/detect-tests")
def detect_tests(
    req: DetectTestsRequest
):

    return services.detect_tests(
        Path(req.repo_path)
    )


# ============================================================
# DAY 12 — VALIDATION
# ============================================================

@app.post("/validate")
def validate_repository(
    req: ValidateRequest
):

    return services.validate_repository(
        Path(req.repo_path)
    )