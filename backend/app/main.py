import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .services import (
    ingest_repo,
    analyze_repo,
    chunk_repo,
    retrieve_chunks,
    build_context,
    ask_codebase,
    get_relationships,
    investigate_bug,
    plan_feature,
    propose_change,
    engineer_workflow,
    detect_tests,
    validate_repository,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("ai-codebase-engineer")


# ============================================================
# APP CONFIGURATION
# ============================================================

APP_NAME = "AI Codebase Engineer"

cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in cors_origins.split(",")
    if origin.strip()
]


# ============================================================
# RATE LIMITING
# ============================================================

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        "60/minute"
    ],
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title=APP_NAME,
    version="1.0.0",
    description=(
        "AI-powered software repository analysis, "
        "investigation, planning and code-change engine."
    ),
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
    ],
    allow_headers=[
        "Content-Type",
        "Authorization",
    ],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class IngestRequest(BaseModel):
    repo_url: str = Field(min_length=1)


class AnalyzeRequest(BaseModel):
    cloned_to: str = Field(min_length=1)


class ChunkRequest(BaseModel):
    repo_path: str = Field(min_length=1)


class RetrieveRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class ContextRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class PromptRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class AskRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class RelationshipsRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    name: str = Field(min_length=1)


class InvestigateRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    bug_description: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class PlanRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    feature_request: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class ProposeChangeRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    instruction: str = Field(min_length=1)


class EngineerRequest(BaseModel):
    repo_url: str = Field(min_length=1)

    task_type: Literal[
        "ask",
        "investigate",
        "plan",
    ] = "ask"

    question: str = Field(min_length=1)

    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
    )


class DetectTestsRequest(BaseModel):
    repo_path: str = Field(min_length=1)


class ValidateRequest(BaseModel):
    repo_path: str = Field(min_length=1)


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():
    logger.info("Root endpoint called")

    return {
        "message": f"{APP_NAME} API is running.",
        "version": "1.0.0",
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
@limiter.limit("10/minute")
def ingest(
    request: Request,
    body: IngestRequest,
):
    logger.info(
        "Ingest requested: %s",
        body.repo_url,
    )

    return ingest_repo(
        body.repo_url
    )


# ============================================================
# ANALYZE
# ============================================================

@app.post("/analyze")
@limiter.limit("20/minute")
def analyze(
    request: Request,
    body: AnalyzeRequest,
):
    return analyze_repo(
        Path(body.cloned_to)
    )


# ============================================================
# CHUNK
# ============================================================

@app.post("/chunk")
@limiter.limit("20/minute")
def chunk(
    request: Request,
    body: ChunkRequest,
):
    logger.info(
        "Chunk requested: %s",
        body.repo_path,
    )

    return chunk_repo(
        Path(body.repo_path)
    )


# ============================================================
# RETRIEVE
# ============================================================

@app.post("/retrieve")
@limiter.limit("30/minute")
def retrieve(
    request: Request,
    body: RetrieveRequest,
):
    return retrieve_chunks(
        Path(body.repo_path),
        body.query,
        body.top_k,
    )


# ============================================================
# CONTEXT
# ============================================================

@app.post("/context")
@limiter.limit("30/minute")
def context(
    request: Request,
    body: ContextRequest,
):
    return build_context(
        Path(body.repo_path),
        body.query,
        body.top_k,
    )


# ============================================================
# PROMPT
# ============================================================

@app.post("/prompt")
@limiter.limit("30/minute")
def prompt(
    request: Request,
    body: PromptRequest,
):
    chunks = retrieve_chunks(
        Path(body.repo_path),
        body.question,
        body.top_k,
    )

    context_parts = []

    for result in chunks.get("results", []):
        chunk = result["chunk"]

        context_parts.append(
            f"""FILE: {chunk.get("file")}
TYPE: {chunk.get("type")}
NAME: {chunk.get("name")}
LINES: {chunk.get("start_line")}-{chunk.get("end_line")}

CODE:
{chunk.get("content")}
"""
        )

    context_text = "\n---\n".join(
        context_parts
    )

    prompt_text = f"""You are an AI Codebase Engineer.

Use the provided code context as your primary source.

Do not invent files, functions, classes, or behavior.

USER QUESTION:
{body.question}

CODEBASE CONTEXT:
{context_text}
"""

    return {
        "success": True,
        "question": body.question,
        "retrieved_chunks": len(
            chunks.get("results", [])
        ),
        "prompt": prompt_text,
    }


# ============================================================
# ASK
# ============================================================

@app.post("/ask")
@limiter.limit("10/minute")
def ask(
    request: Request,
    body: AskRequest,
):
    logger.info(
        "Ask requested: %s",
        body.question,
    )

    return ask_codebase(
        Path(body.repo_path),
        body.question,
        body.top_k,
    )


# ============================================================
# RELATIONSHIPS
# ============================================================

@app.post("/relationships")
@limiter.limit("30/minute")
def relationships(
    request: Request,
    body: RelationshipsRequest,
):
    return get_relationships(
        Path(body.repo_path),
        body.name,
    )


# ============================================================
# INVESTIGATE
# ============================================================

@app.post("/investigate")
@limiter.limit("10/minute")
def investigate(
    request: Request,
    body: InvestigateRequest,
):
    logger.info(
        "Investigation requested"
    )

    return investigate_bug(
        Path(body.repo_path),
        body.bug_description,
        body.top_k,
    )


# ============================================================
# PLAN
# ============================================================

@app.post("/plan")
@limiter.limit("10/minute")
def plan(
    request: Request,
    body: PlanRequest,
):
    logger.info(
        "Plan requested"
    )

    return plan_feature(
        Path(body.repo_path),
        body.feature_request,
        body.top_k,
    )


# ============================================================
# PROPOSE CHANGE
# ============================================================

@app.post("/propose-change")
@limiter.limit("10/minute")
def propose_change_route(
    request: Request,
    body: ProposeChangeRequest,
):
    logger.info(
        "Code change proposed for %s",
        body.file_path,
    )

    return propose_change(
        Path(body.repo_path),
        body.file_path,
        body.instruction,
    )


# ============================================================
# DAY 12 — DETECT TESTS
# ============================================================

@app.post("/detect-tests")
@limiter.limit("20/minute")
def detect_tests_route(
    request: Request,
    body: DetectTestsRequest,
):
    logger.info(
        "Test detection requested: %s",
        body.repo_path,
    )

    return detect_tests(
        Path(body.repo_path)
    )


# ============================================================
# DAY 12 — VALIDATE
# ============================================================

@app.post("/validate")
@limiter.limit("10/minute")
def validate_repository_route(
    request: Request,
    body: ValidateRequest,
):
    logger.info(
        "Repository validation requested: %s",
        body.repo_path,
    )

    return validate_repository(
        Path(body.repo_path)
    )


# ============================================================
# DAY 13 — ENGINEER
# ============================================================

@app.post("/engineer")
@limiter.limit("5/minute")
def engineer(
    request: Request,
    body: EngineerRequest,
):
    logger.info(
        "Engineer workflow started: task=%s",
        body.task_type,
    )

    result = engineer_workflow(
        repo_url=body.repo_url,
        task_type=body.task_type,
        question=body.question,
        top_k=body.top_k,
    )

    logger.info(
        "Engineer workflow finished: success=%s",
        result.get("success"),
    )

    return result