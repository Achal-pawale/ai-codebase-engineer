from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
)


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


class ContextRequest(BaseModel):
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


# ============================================================
# DAY 13 — ENGINEER REQUEST
# ============================================================

class EngineerRequest(BaseModel):

    repo_url: str

    task_type: Literal[
        "ask",
        "investigate",
        "plan"
    ] = "ask"

    question: str

    top_k: int = 5


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():

    return {
        "message":
            "AI Codebase Engineer API is running."
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
def ingest(request: IngestRequest):

    return ingest_repo(
        request.repo_url
    )


# ============================================================
# ANALYZE
# ============================================================

@app.post("/analyze")
def analyze(request: AnalyzeRequest):

    return analyze_repo(
        Path(request.cloned_to)
    )


# ============================================================
# CHUNK
# ============================================================

@app.post("/chunk")
def chunk(request: ChunkRequest):

    return chunk_repo(
        Path(request.repo_path)
    )


# ============================================================
# RETRIEVE
# ============================================================

@app.post("/retrieve")
def retrieve(request: RetrieveRequest):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    try:

        return retrieve_chunks(
            repo_path,
            request.query,
            request.top_k
        )

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# CONTEXT
# ============================================================

@app.post("/context")
def context(request: ContextRequest):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    try:

        return build_context(
            repo_path,
            request.query,
            request.top_k
        )

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# PROMPT
# ============================================================

@app.post("/prompt")
def prompt(request: PromptRequest):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    try:

        chunks = retrieve_chunks(
            repo_path,
            request.question,
            request.top_k
        )

        context_text = ""

        for result in chunks.get(
            "results",
            []
        ):

            chunk = result["chunk"]

            context_text += (
                f"\nFILE: {chunk.get('file')}\n"
                f"TYPE: {chunk.get('type')}\n"
                f"NAME: {chunk.get('name')}\n"
                f"LINES: "
                f"{chunk.get('start_line')}-"
                f"{chunk.get('end_line')}\n\n"
                f"{chunk.get('content')}\n"
            )

        prompt_text = f"""You are an AI Codebase Engineer.

Use the provided code context as your primary source.

Do not invent files, functions, classes, or behavior.

USER QUESTION:
{request.question}

CODEBASE CONTEXT:
{context_text}
"""

        return {
            "success": True,
            "question":
                request.question,
            "retrieved_chunks":
                len(
                    chunks.get(
                        "results",
                        []
                    )
                ),
            "prompt":
                prompt_text
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# ASK
# ============================================================

@app.post("/ask")
def ask(request: AskRequest):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    try:

        return ask_codebase(
            repo_path,
            request.question,
            request.top_k
        )

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
        }

    except Exception as e:

        return {
            "success": False,
            "error":
                f"LLM call failed: {e}"
        }


# ============================================================
# RELATIONSHIPS
# ============================================================

@app.post("/relationships")
def relationships(
    request: RelationshipsRequest
):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    try:

        return get_relationships(
            repo_path,
            request.name
        )

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# INVESTIGATE
# ============================================================

@app.post("/investigate")
def investigate(
    request: InvestigateRequest
):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    try:

        return investigate_bug(
            repo_path,
            request.bug_description,
            request.top_k
        )

    except Exception as e:

        return {
            "success": False,
            "error":
                f"LLM call failed: {e}"
        }


# ============================================================
# PLAN
# ============================================================

@app.post("/plan")
def plan(
    request: PlanRequest
):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    try:

        return plan_feature(
            repo_path,
            request.feature_request,
            request.top_k
        )

    except Exception as e:

        return {
            "success": False,
            "error":
                f"LLM call failed: {e}"
        }


# ============================================================
# PROPOSE CHANGE
# ============================================================

@app.post("/propose-change")
def propose_change_route(
    request: ProposeChangeRequest
):

    repo_path = Path(
        request.repo_path
    )

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    if not request.instruction.strip():

        return {
            "success": False,
            "error":
                "instruction cannot be empty."
        }

    try:

        return propose_change(
            repo_path,
            request.file_path,
            request.instruction
        )

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# DAY 13 — END-TO-END ENGINEER
# ============================================================

@app.post("/engineer")
def engineer(
    request: EngineerRequest
):

    if not request.repo_url.strip():

        return {
            "success": False,
            "error":
                "repo_url cannot be empty."
        }

    if not request.question.strip():

        return {
            "success": False,
            "error":
                "question cannot be empty."
        }

    if request.top_k < 1:

        return {
            "success": False,
            "error":
                "top_k must be at least 1."
        }

    try:

        return engineer_workflow(
            repo_url=
                request.repo_url,
            task_type=
                request.task_type,
            question=
                request.question,
            top_k=
                request.top_k
        )

    except Exception as e:

        return {
            "success": False,
            "stage":
                "engineer",
            "error":
                str(e)
        }