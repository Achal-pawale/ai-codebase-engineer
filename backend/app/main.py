from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
from google import genai

import subprocess
import shutil
import os
import stat
import ast
import json
import difflib
import time
import tempfile

# ============================================================
# CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found in backend/.env"
    )

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# GEMINI
# ============================================================

def call_gemini_with_retry(prompt: str, max_retries: int = 3):
    """
    Calls Gemini, retrying with a short backoff on transient errors
    like 503 UNAVAILABLE.

    Fails immediately on non-transient errors.
    """

    last_error = None

    for attempt in range(max_retries):

        try:

            return gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )

        except Exception as e:

            last_error = e
            error_text = str(e)

            if (
                "503" not in error_text
                and "UNAVAILABLE" not in error_text
            ):
                raise

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    raise last_error


# ============================================================
# FASTAPI
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
# DIRECTORIES
# ============================================================

WORKSPACE_DIR = BACKEND_DIR / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PROPOSED_CHANGES_DIR = BACKEND_DIR / "proposed_changes"
PROPOSED_CHANGES_DIR.mkdir(exist_ok=True)


def chunks_path_for(repo_path: Path) -> Path:
    return DATA_DIR / f"{repo_path.name}_chunks.json"


# ============================================================
# REPOSITORY CONFIGURATION
# ============================================================

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
}


CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".cs",
}


# ============================================================
# DAY 12 TEST CONFIGURATION
# ============================================================

MAX_TEST_TIMEOUT = 300

MAX_OUTPUT_SIZE = 50_000


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
# DAY 12 REQUEST MODELS
# ============================================================

class DetectTestsRequest(BaseModel):
    repo_path: str


class ValidateRequest(BaseModel):
    repo_path: str
    top_k: int = 5
    timeout_seconds: int = 120


# ============================================================
# ROOT / HEALTH
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

def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


@app.post("/ingest")
def ingest_repo(req: IngestRequest):

    repo_name = req.repo_url.rstrip("/").split("/")[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    dest = WORKSPACE_DIR / repo_name

    if dest.exists():

        shutil.rmtree(
            dest,
            onerror=remove_readonly
        )

    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            req.repo_url,
            str(dest)
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:

        return {
            "success": False,
            "error": result.stderr
        }

    top_level = [
        item.name
        for item in dest.iterdir()
        if item.name not in IGNORE_DIRS
    ]

    file_count = 0

    for root, dirs, files in os.walk(dest):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORE_DIRS
        ]

        file_count += len(files)

    return {
        "success": True,
        "cloned_to": str(dest),
        "top_level_items": sorted(top_level),
        "file_count": file_count
    }


# ============================================================
# ANALYZE
# ============================================================

@app.post("/analyze")
def analyze_repo(req: AnalyzeRequest):

    repo_path = Path(req.cloned_to)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "That path doesn't exist. Ingest the repo first."
        }

    if not repo_path.is_dir():

        return {
            "success": False,
            "error": "Repository path is not a directory."
        }

    files_info = []

    language_counts = {}

    directories = set()

    important_names = {
        "README",
        "README.md",
        "README.txt",
        "requirements.txt",
        "package.json",
        "pyproject.toml",
        "setup.py",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".env.example",
        "Makefile",
    }

    important_files = []

    for root, dirs, files in os.walk(repo_path):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORE_DIRS
        ]

        current_root = Path(root)

        if current_root != repo_path:

            relative_dir = current_root.relative_to(
                repo_path
            )

            directories.add(
                str(relative_dir)
            )

        for filename in files:

            file_path = current_root / filename

            if filename in important_names:

                relative_path = file_path.relative_to(
                    repo_path
                )

                important_files.append(
                    str(relative_path)
                )

            extension = file_path.suffix.lower()

            if extension in CODE_EXTENSIONS:

                relative_path = file_path.relative_to(
                    repo_path
                )

                size = file_path.stat().st_size

                files_info.append({
                    "path": str(relative_path),
                    "extension": extension,
                    "size_bytes": size
                })

                language_counts[extension] = (
                    language_counts.get(extension, 0) + 1
                )

    return {
        "success": True,
        "summary": {
            "total_code_files": len(files_info),
            "language_counts": language_counts,
            "directory_count": len(directories),
            "important_files": sorted(
                important_files
            )
        },
        "directories": sorted(directories),
        "files": files_info
    }


# ============================================================
# CHUNK
# ============================================================

@app.post("/chunk")
def chunk_repo(req: ChunkRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    if not repo_path.is_dir():

        return {
            "success": False,
            "error": "Repository path is not a directory."
        }

    all_chunks = []

    files_processed = 0

    files_skipped = 0

    for root, dirs, files in os.walk(repo_path):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORE_DIRS
        ]

        for filename in files:

            file_path = Path(root) / filename

            extension = file_path.suffix.lower()

            if extension not in CODE_EXTENSIONS:

                files_skipped += 1
                continue

            if extension != ".py":

                files_skipped += 1
                continue

            try:

                content = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

                tree = ast.parse(content)

                lines = content.splitlines()

                relative_path = file_path.relative_to(
                    repo_path
                )

                imports = []

                for node in ast.walk(tree):

                    if isinstance(
                        node,
                        ast.Import
                    ):

                        for alias in node.names:
                            imports.append(alias.name)

                    elif isinstance(
                        node,
                        ast.ImportFrom
                    ):

                        if node.module:
                            imports.append(
                                node.module
                            )

                imports = sorted(
                    set(imports)
                )

                for node in ast.walk(tree):

                    if not isinstance(
                        node,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.ClassDef
                        )
                    ):
                        continue

                    start_line = node.lineno

                    end_line = getattr(
                        node,
                        "end_lineno",
                        node.lineno
                    )

                    chunk_content = "\n".join(
                        lines[
                            start_line - 1:end_line
                        ]
                    )

                    if isinstance(
                        node,
                        ast.ClassDef
                    ):

                        structure_type = "class"

                    elif isinstance(
                        node,
                        ast.AsyncFunctionDef
                    ):

                        structure_type = "async_function"

                    else:

                        structure_type = "function"

                    references = []

                    for child in ast.walk(node):

                        if isinstance(
                            child,
                            ast.Name
                        ):

                            references.append(
                                child.id
                            )

                        elif isinstance(
                            child,
                            ast.Attribute
                        ):

                            references.append(
                                child.attr
                            )

                    references = sorted(
                        set(references)
                    )

                    all_chunks.append({

                        "chunk_id":
                            len(all_chunks) + 1,

                        "type":
                            structure_type,

                        "name":
                            node.name,

                        "file":
                            str(relative_path),

                        "language":
                            "python",

                        "imports":
                            imports,

                        "references":
                            references,

                        "start_line":
                            start_line,

                        "end_line":
                            end_line,

                        "content":
                            chunk_content
                    })

                files_processed += 1

            except SyntaxError:

                files_skipped += 1

            except Exception:

                files_skipped += 1

    chunks_file = chunks_path_for(repo_path)

    with open(
        chunks_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "repository":
                    str(repo_path),

                "total_chunks":
                    len(all_chunks),

                "chunks":
                    all_chunks
            },
            f,
            indent=2,
            ensure_ascii=False
        )

    return {

        "success":
            True,

        "repository":
            str(repo_path),

        "files_processed":
            files_processed,

        "files_skipped":
            files_skipped,

        "total_chunks":
            len(all_chunks),

        "chunks_file":
            str(chunks_file),

        "chunks":
            all_chunks
    }


# ============================================================
# RETRIEVE
# ============================================================

@app.post("/retrieve")
def retrieve_chunks(req: RetrieveRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():

        return {
            "success": False,
            "error": "chunks.json not found. Run /chunk first."
        }

    query = req.query.strip().lower()

    if not query:

        return {
            "success": False,
            "error": "Query cannot be empty."
        }

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        chunks = data.get("chunks", [])

        query_words = query.split()

        results = []

        for chunk in chunks:

            name = str(
                chunk.get("name", "")
            ).lower()

            file_path = str(
                chunk.get("file", "")
            ).lower()

            chunk_type = str(
                chunk.get("type", "")
            ).lower()

            content = str(
                chunk.get("content", "")
            ).lower()

            imports = " ".join(
                chunk.get("imports", [])
            ).lower()

            references = " ".join(
                chunk.get("references", [])
            ).lower()

            matched_words = []

            for word in query_words:

                if word in name:
                    matched_words.append(word)

                elif word in file_path:
                    matched_words.append(word)

                elif word in content:
                    matched_words.append(word)

                elif word in imports:
                    matched_words.append(word)

                elif word in references:
                    matched_words.append(word)

            matched_words = sorted(
                set(matched_words)
            )

            if not matched_words:
                continue

            score = 0

            if query == name:
                score += 20

            elif query in name:
                score += 12

            name_matches = sum(
                1
                for word in query_words
                if word in name
            )

            score += name_matches * 8

            if query in file_path:
                score += 10

            file_matches = sum(
                1
                for word in query_words
                if word in file_path
            )

            score += file_matches * 4

            reference_matches = sum(
                1
                for word in query_words
                if word in references
            )

            score += reference_matches * 5

            import_matches = sum(
                1
                for word in query_words
                if word in imports
            )

            score += import_matches * 3

            content_matches = sum(
                1
                for word in query_words
                if word in content
            )

            score += content_matches

            if chunk_type in {
                "function",
                "async_function"
            }:

                score += 2

            elif chunk_type == "class":

                score += 1

            start_line = chunk.get(
                "start_line",
                0
            )

            end_line = chunk.get(
                "end_line",
                start_line
            )

            try:

                line_count = (
                    int(end_line)
                    - int(start_line)
                    + 1
                )

            except Exception:

                line_count = 1

            if line_count > 500:
                score -= 5

            elif line_count > 250:
                score -= 3

            results.append({
                "score": score,
                "matched_words": matched_words,
                "chunk": chunk
            })

        results.sort(
            key=lambda result: (
                result["score"],
                -(
                    result["chunk"].get(
                        "end_line",
                        0
                    )
                    -
                    result["chunk"].get(
                        "start_line",
                        0
                    )
                )
            ),
            reverse=True
        )

        results = results[:req.top_k]

        return {
            "success": True,
            "query": req.query,
            "match_count": len(results),
            "results": results
        }

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# CONTEXT HELPER
# ============================================================

def build_context_from_chunks(results):

    context_parts = []

    for result in results:

        chunk = result["chunk"]

        context_parts.append(
            f"""FILE: {chunk.get("file")}
LANGUAGE: {chunk.get("language")}
TYPE: {chunk.get("type")}
NAME: {chunk.get("name")}
LINES: {chunk.get("start_line")}-{chunk.get("end_line")}

IMPORTS:
{", ".join(chunk.get("imports", []))}

REFERENCES:
{", ".join(chunk.get("references", []))}

CODE:
{chunk.get("content")}
"""
        )

    if not context_parts:

        return (
            "No relevant code was found "
            "for this question."
        )

    return "\n---\n".join(
        context_parts
    )


# ============================================================
# CONTEXT
# ============================================================

@app.post("/context")
def build_context(req: RetrieveRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():

        return {
            "success": False,
            "error": "chunks.json not found. Run /chunk first."
        }

    query = req.query.strip()

    if not query:

        return {
            "success": False,
            "error": "Query cannot be empty."
        }

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        chunks = data.get("chunks", [])

        query_lower = query.lower()

        query_words = query_lower.split()

        results = []

        for chunk in chunks:

            name = str(
                chunk.get("name", "")
            ).lower()

            file_path = str(
                chunk.get("file", "")
            ).lower()

            chunk_type = str(
                chunk.get("type", "")
            ).lower()

            content = str(
                chunk.get("content", "")
            ).lower()

            imports = " ".join(
                chunk.get("imports", [])
            ).lower()

            references = " ".join(
                chunk.get("references", [])
            ).lower()

            matched_words = []

            for word in query_words:

                if word in name:
                    matched_words.append(word)

                elif word in file_path:
                    matched_words.append(word)

                elif word in content:
                    matched_words.append(word)

                elif word in imports:
                    matched_words.append(word)

                elif word in references:
                    matched_words.append(word)

            matched_words = sorted(
                set(matched_words)
            )

            if not matched_words:
                continue

            score = 0

            if query_lower == name:
                score += 20

            elif query_lower in name:
                score += 12

            name_matches = sum(
                1
                for word in query_words
                if word in name
            )

            score += name_matches * 8

            if query_lower in file_path:
                score += 10

            file_matches = sum(
                1
                for word in query_words
                if word in file_path
            )

            score += file_matches * 4

            reference_matches = sum(
                1
                for word in query_words
                if word in references
            )

            score += reference_matches * 5

            import_matches = sum(
                1
                for word in query_words
                if word in imports
            )

            score += import_matches * 3

            content_matches = sum(
                1
                for word in query_words
                if word in content
            )

            score += content_matches

            if chunk_type in {
                "function",
                "async_function"
            }:

                score += 2

            elif chunk_type == "class":

                score += 1

            start_line = chunk.get(
                "start_line",
                0
            )

            end_line = chunk.get(
                "end_line",
                start_line
            )

            try:

                line_count = (
                    int(end_line)
                    - int(start_line)
                    + 1
                )

            except Exception:

                line_count = 1

            if line_count > 500:
                score -= 5

            elif line_count > 250:
                score -= 3

            results.append({
                "score": score,
                "matched_words": matched_words,
                "chunk": chunk
            })

        results.sort(
            key=lambda result: (
                result["score"],
                -(
                    result["chunk"].get(
                        "end_line",
                        0
                    )
                    -
                    result["chunk"].get(
                        "start_line",
                        0
                    )
                )
            ),
            reverse=True
        )

        results = results[:req.top_k]

        context_parts = []

        for result in results:

            chunk = result["chunk"]

            part = f"""FILE: {chunk.get("file")}
LANGUAGE: {chunk.get("language")}
TYPE: {chunk.get("type")}
NAME: {chunk.get("name")}
LINES: {chunk.get("start_line")}-{chunk.get("end_line")}

IMPORTS:
{", ".join(chunk.get("imports", []))}

REFERENCES:
{", ".join(chunk.get("references", []))}

CODE:
{chunk.get("content")}
"""

            context_parts.append(part)

        context = "\n\n".join(
            context_parts
        )

        return {
            "success": True,
            "query": req.query,
            "chunk_count": len(results),
            "context": context
        }

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
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
def build_prompt(req: PromptRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():

        return {
            "success": False,
            "error": "chunks.json not found. Run /chunk first."
        }

    question = req.question.strip()

    if not question:

        return {
            "success": False,
            "error": "Question cannot be empty."
        }

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        chunks = data.get(
            "chunks",
            []
        )

        query = question.lower()

        query_words = query.split()

        results = []

        for chunk in chunks:

            searchable_text = " ".join([
                str(chunk.get("name", "")),
                str(chunk.get("type", "")),
                str(chunk.get("file", "")),
                str(chunk.get("content", "")),
                " ".join(
                    chunk.get("imports", [])
                ),
                " ".join(
                    chunk.get("references", [])
                )
            ]).lower()

            matched_words = [
                word
                for word in query_words
                if word in searchable_text
            ]

            if not matched_words:
                continue

            score = len(
                matched_words
            )

            name = str(
                chunk.get("name", "")
            ).lower()

            if query in name:
                score += 5

            content = str(
                chunk.get("content", "")
            ).lower()

            if query in content:
                score += 3

            results.append({
                "score": score,
                "chunk": chunk
            })

        results.sort(
            key=lambda result:
                result["score"],
            reverse=True
        )

        results = results[:req.top_k]

        context_parts = []

        for result in results:

            chunk = result["chunk"]

            context_parts.append(
                f"""FILE: {chunk.get("file")}
LANGUAGE: {chunk.get("language")}
TYPE: {chunk.get("type")}
NAME: {chunk.get("name")}
LINES: {chunk.get("start_line")}-{chunk.get("end_line")}

CODE:
{chunk.get("content")}
"""
            )

        context = "\n---\n".join(
            context_parts
        )

        prompt = f"""You are an AI Codebase Engineer.

Your job is to answer questions about a software
repository using the provided code context.

Rules:
- Use the provided code context as your primary source.
- Do not invent files, functions, classes, or behavior.
- If the context does not contain enough information,
  clearly say so.
- Mention relevant file names when useful.
- When you reference code, cite it inline like (file.py, lines 10-15).
- Clearly separate what the code shows (evidence) from anything you are inferring.
- Explain the code clearly and concisely.

USER QUESTION:
{req.question}

CODEBASE CONTEXT:
{context}
"""

        return {
            "success": True,
            "question": req.question,
            "retrieved_chunks": len(results),
            "prompt": prompt
        }

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
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
def ask_codebase(req: AskRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():

        return {
            "success": False,
            "error": "chunks.json not found. Run /chunk first."
        }

    question = req.question.strip()

    if not question:

        return {
            "success": False,
            "error": "Question cannot be empty."
        }

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        chunks = data.get(
            "chunks",
            []
        )

        query = question.lower()

        query_words = query.split()

        results = []

        for chunk in chunks:

            searchable_text = " ".join([
                str(chunk.get("name", "")),
                str(chunk.get("type", "")),
                str(chunk.get("file", "")),
                str(chunk.get("content", "")),
                " ".join(
                    chunk.get("imports", [])
                ),
                " ".join(
                    chunk.get("references", [])
                )
            ]).lower()

            matched_words = [
                word
                for word in query_words
                if word in searchable_text
            ]

            if not matched_words:
                continue

            score = len(
                matched_words
            )

            name = str(
                chunk.get("name", "")
            ).lower()

            if query in name:
                score += 5

            content = str(
                chunk.get("content", "")
            ).lower()

            if query in content:
                score += 3

            results.append({
                "score": score,
                "chunk": chunk
            })

        results.sort(
            key=lambda result:
                result["score"],
            reverse=True
        )

        results = results[:req.top_k]

        context = build_context_from_chunks(
            results
        )

        prompt = f"""You are an AI Codebase Engineer.

Your job is to answer questions about a software
repository using the provided code context.

Rules:
- Use the provided code context as your primary source.
- Do not invent files, functions, classes, or behavior.
- If the context does not contain enough information,
  clearly say so.
- Mention relevant file names when useful.
- When you reference code, cite it inline like (file.py, lines 10-15).
- Clearly separate what the code shows (evidence) from anything you are inferring.
- Explain the code clearly and concisely.

USER QUESTION:
{question}

CODEBASE CONTEXT:
{context}
"""

        response = call_gemini_with_retry(
            prompt
        )

        answer = response.text

        sources = [
            result["chunk"]["file"]
            for result in results
        ]

        return {

            "success":
                True,

            "question":
                question,

            "answer":
                answer,

            "retrieved_chunks":
                len(results),

            "model":
                GEMINI_MODEL,

            "sources":
                sorted(set(sources))
        }

    except json.JSONDecodeError:

        return {
            "success": False,
            "error":
                "chunks.json contains invalid JSON."
        }

    except Exception as e:

        return {
            "success": False,
            "error":
                str(e)
        }


# ============================================================
# RELATIONSHIPS
# ============================================================

@app.post("/relationships")
def get_relationships(req: RelationshipsRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():

        return {
            "success": False,
            "error": "chunks.json not found. Run /chunk first."
        }

    target_name = req.name.strip()

    if not target_name:

        return {
            "success": False,
            "error": "Name cannot be empty."
        }

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

    chunks = data.get(
        "chunks",
        []
    )

    defined_at = [
        {
            "file": chunk.get("file"),
            "type": chunk.get("type"),
            "start_line": chunk.get("start_line"),
            "end_line": chunk.get("end_line"),
        }
        for chunk in chunks
        if chunk.get("name") == target_name
    ]

    depends_on = set()

    for chunk in chunks:

        if chunk.get("name") == target_name:

            depends_on.update(
                chunk.get(
                    "references",
                    []
                )
            )

            depends_on.update(
                chunk.get(
                    "imports",
                    []
                )
            )

    used_by = []

    for chunk in chunks:

        if chunk.get("name") == target_name:
            continue

        if target_name in chunk.get(
            "references",
            []
        ):

            used_by.append({
                "name": chunk.get("name"),
                "file": chunk.get("file"),
                "type": chunk.get("type"),
                "start_line": chunk.get("start_line"),
                "end_line": chunk.get("end_line"),
            })

    imported_in_files = sorted({
        chunk.get("file")
        for chunk in chunks
        if target_name in chunk.get(
            "imports",
            []
        )
    })

    return {
        "success": True,
        "name": target_name,
        "defined_at": defined_at,
        "depends_on": sorted(
            depends_on
        ),
        "used_by": used_by,
        "imported_in_files": imported_in_files,
    }


# ============================================================
# INVESTIGATE
# ============================================================

@app.post("/investigate")
def investigate_bug(req: InvestigateRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():

        return {
            "success": False,
            "error": "chunks.json not found. Run /chunk first."
        }

    bug_description = req.bug_description.strip()

    if not bug_description:

        return {
            "success": False,
            "error": "bug_description cannot be empty."
        }

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

    chunks = data.get(
        "chunks",
        []
    )

    query = bug_description.lower()

    query_words = query.split()

    results = []

    for chunk in chunks:

        searchable_text = " ".join([
            str(chunk.get("name", "")),
            str(chunk.get("type", "")),
            str(chunk.get("file", "")),
            str(chunk.get("content", "")),
            " ".join(
                chunk.get("imports", [])
            ),
            " ".join(
                chunk.get("references", [])
            )
        ]).lower()

        matched_words = [
            w
            for w in query_words
            if w in searchable_text
        ]

        if not matched_words:
            continue

        score = len(
            matched_words
        )

        name = str(
            chunk.get("name", "")
        ).lower()

        if query in name:
            score += 5

        content = str(
            chunk.get("content", "")
        ).lower()

        if query in content:
            score += 3

        results.append({
            "score": score,
            "chunk": chunk
        })

    results.sort(
        key=lambda r: r["score"],
        reverse=True
    )

    results = results[:req.top_k]

    if not results:

        return {
            "success": True,
            "bug_description": bug_description,
            "investigation": (
                "No relevant code was found for this bug description. "
                "Try describing it with terms more likely to appear in "
                "the code (function names, error messages, feature names)."
            ),
            "retrieved_chunks": 0,
            "related_symbols": [],
            "sources": [],
        }

    related_notes = []

    related_symbol_names = set()

    for result in results:

        chunk = result["chunk"]

        name = chunk.get("name")

        if not name or name in related_symbol_names:
            continue

        related_symbol_names.add(name)

        used_by = [
            c.get("name")
            for c in chunks
            if c.get("name") != name
            and name in c.get(
                "references",
                []
            )
        ]

        if used_by:

            related_notes.append(
                f"{name} (in {chunk.get('file')}) "
                f"is used by: "
                f"{', '.join(sorted(set(used_by))[:5])}"
            )

    related_context = (
        "\n".join(related_notes)
        if related_notes
        else
        "No cross-references found among the retrieved code."
    )

    context = build_context_from_chunks(
        results
    )

    prompt = f"""You are an AI Codebase Engineer investigating a reported bug.

Use ONLY the code shown below. Do not invent files, functions, or
behavior that isn't shown. If the code doesn't support a conclusion,
say so honestly instead of guessing.

Respond in exactly this structure:

SUSPECTED CAUSE:
<your best hypothesis, or "Unable to determine from available code">

EVIDENCE:
<specific code supporting this, cited inline like (file.py, lines X-Y)>

FILES TO CHECK NEXT:
<a short list of files/functions worth investigating further, and why>

CONFIDENCE:
<High / Medium / Low, with a one-line reason>

BUG DESCRIPTION:
{bug_description}

RELEVANT CODE:
{context}

CROSS-REFERENCES (what else touches this code):
{related_context}
"""

    try:

        response = call_gemini_with_retry(
            prompt
        )

        investigation = response.text

    except Exception as e:

        return {
            "success": False,
            "error": f"LLM call failed: {e}"
        }

    sources = sorted({
        result["chunk"]["file"]
        for result in results
    })

    return {
        "success": True,
        "bug_description": bug_description,
        "investigation": investigation,
        "retrieved_chunks": len(results),
        "related_symbols": sorted(
            related_symbol_names
        ),
        "sources": sources,
        "model": GEMINI_MODEL,
    }


# ============================================================
# PLAN
# ============================================================

@app.post("/plan")
def plan_feature(req: PlanRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():

        return {
            "success": False,
            "error": "chunks.json not found. Run /chunk first."
        }

    feature_request = req.feature_request.strip()

    if not feature_request:

        return {
            "success": False,
            "error": "feature_request cannot be empty."
        }

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

    chunks = data.get(
        "chunks",
        []
    )

    query = feature_request.lower()

    query_words = query.split()

    results = []

    for chunk in chunks:

        searchable_text = " ".join([
            str(chunk.get("name", "")),
            str(chunk.get("type", "")),
            str(chunk.get("file", "")),
            str(chunk.get("content", "")),
            " ".join(
                chunk.get("imports", [])
            ),
            " ".join(
                chunk.get("references", [])
            )
        ]).lower()

        matched_words = [
            w
            for w in query_words
            if w in searchable_text
        ]

        if not matched_words:
            continue

        score = len(
            matched_words
        )

        name = str(
            chunk.get("name", "")
        ).lower()

        if query in name:
            score += 5

        content = str(
            chunk.get("content", "")
        ).lower()

        if query in content:
            score += 3

        results.append({
            "score": score,
            "chunk": chunk
        })

    results.sort(
        key=lambda r: r["score"],
        reverse=True
    )

    results = results[:req.top_k]

    if not results:

        return {
            "success": True,
            "feature_request": feature_request,
            "plan": (
                "No closely related existing code was found for this "
                "feature request. This may mean it's a genuinely new "
                "capability with little to build on, or that it needs "
                "to be described using terms closer to the actual code "
                "(function names, module names, existing feature names)."
            ),
            "retrieved_chunks": 0,
            "related_symbols": [],
            "sources": [],
        }

    related_notes = []

    related_symbol_names = set()

    for result in results:

        chunk = result["chunk"]

        name = chunk.get("name")

        if not name or name in related_symbol_names:
            continue

        related_symbol_names.add(name)

        used_by = [
            c.get("name")
            for c in chunks
            if c.get("name") != name
            and name in c.get(
                "references",
                []
            )
        ]

        if used_by:

            related_notes.append(
                f"{name} (in {chunk.get('file')}) "
                f"is used by: "
                f"{', '.join(sorted(set(used_by))[:5])} "
                f"— changing it could affect these too."
            )

    related_context = (
        "\n".join(related_notes)
        if related_notes
        else
        "No cross-references found among the retrieved code."
    )

    context = build_context_from_chunks(
        results
    )

    prompt = f"""You are an AI Codebase Engineer, planning a new feature
before any code is written.

Use ONLY the code shown below. Do not invent files, functions, or
behavior that isn't shown. If the codebase context isn't enough to
plan this confidently, say so honestly instead of guessing.

Respond in exactly this structure:

AFFECTED FILES:
<files/functions this feature would likely touch, and why>

PROPOSED CHANGES:
<a concrete outline of what would need to change, cited inline like (file.py, lines X-Y) where relevant>

RISKS:
<what could break, edge cases, or existing behavior to be careful of — use the cross-references below>

TESTS TO CONSIDER:
<what should be tested to confirm this works and nothing else broke>

FEATURE REQUEST:
{feature_request}

RELEVANT EXISTING CODE:
{context}

CROSS-REFERENCES (what else touches this code):
{related_context}
"""

    try:

        response = call_gemini_with_retry(
            prompt
        )

        plan = response.text

    except Exception as e:

        return {
            "success": False,
            "error": f"LLM call failed: {e}"
        }

    sources = sorted({
        result["chunk"]["file"]
        for result in results
    })

    return {
        "success": True,
        "feature_request": feature_request,
        "plan": plan,
        "retrieved_chunks": len(results),
        "related_symbols": sorted(
            related_symbol_names
        ),
        "sources": sources,
        "model": GEMINI_MODEL,
    }


# ============================================================
# PROPOSE CHANGE
# ============================================================

def strip_code_fence(text: str) -> str:
    """
    Models sometimes wrap raw file content in markdown code fences.
    """

    check = text.strip()

    if check.startswith("```"):

        lines = check.split("\n")

        lines = lines[1:]

        if lines and lines[-1].strip() == "```":

            lines = lines[:-1]

        return "\n".join(lines) + "\n"

    return text


@app.post("/propose-change")
def propose_change(req: ProposeChangeRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    instruction = req.instruction.strip()

    if not instruction:

        return {
            "success": False,
            "error": "instruction cannot be empty."
        }

    repo_path_resolved = repo_path.resolve()

    target_file = (
        repo_path / req.file_path
    ).resolve()

    try:

        target_file.relative_to(
            repo_path_resolved
        )

    except ValueError:

        return {
            "success": False,
            "error": (
                "file_path escapes the repository folder "
                "— refusing."
            )
        }

    if not target_file.exists():

        return {
            "success": False,
            "error": (
                f"File not found: "
                f"{req.file_path}"
            )
        }

    if not target_file.is_file():

        return {
            "success": False,
            "error": "file_path is not a file."
        }

    try:

        original_content = target_file.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return {
            "success": False,
            "error": (
                "This file is not a readable text file."
            )
        }

    prompt = f"""You are an AI Codebase Engineer making a single, focused code change.

You will be given the CURRENT content of one file and an instruction
describing what to change.

Rules:
- Output ONLY the complete, updated file content.
- Do NOT include markdown code fences, explanations, or commentary.
- Do NOT change anything unrelated to the instruction.
- Preserve existing formatting, comments, and style.
- If the instruction cannot be safely applied, output the original
  content UNCHANGED and nothing else.

FILE: {req.file_path}

INSTRUCTION:
{instruction}

CURRENT FILE CONTENT:
{original_content}
"""

    try:

        response = call_gemini_with_retry(
            prompt
        )

        proposed_content = strip_code_fence(
            response.text
        )

    except Exception as e:

        return {
            "success": False,
            "error": f"LLM call failed: {e}"
        }

    diff_lines = list(
        difflib.unified_diff(
            original_content.splitlines(
                keepends=True
            ),
            proposed_content.splitlines(
                keepends=True
            ),
            fromfile=(
                f"{req.file_path} (current)"
            ),
            tofile=(
                f"{req.file_path} (proposed)"
            ),
        )
    )

    diff_text = "".join(
        diff_lines
    )

    if not diff_text.strip():

        return {
            "success": True,
            "file_path": req.file_path,
            "instruction": instruction,
            "changed": False,
            "message": (
                "The model did not propose "
                "any change to this file."
            ),
            "diff": "",
        }

    safe_name = (
        req.file_path
        .replace("/", "__")
        .replace("\\", "__")
    )

    proposal_file = (
        PROPOSED_CHANGES_DIR
        / f"{repo_path.name}__{safe_name}.proposed"
    )

    proposal_file.write_text(
        proposed_content,
        encoding="utf-8"
    )

    return {
        "success": True,
        "file_path": req.file_path,
        "instruction": instruction,
        "changed": True,
        "diff": diff_text,
        "proposed_file_saved_to": str(
            proposal_file
        ),
        "model": GEMINI_MODEL,
    }


# ============================================================
# ============================================================
# DAY 12 — TEST & VALIDATION ENGINE
# ============================================================
# ============================================================


# ============================================================
# LIMIT TEST OUTPUT
# ============================================================

def limit_output(
    text: str,
    max_size: int = MAX_OUTPUT_SIZE
):
    """
    Prevent enormous test logs from consuming memory
    or creating huge API responses.
    """

    if not text:
        return ""

    if len(text) <= max_size:
        return text

    return (
        text[:max_size]
        + "\n\n"
        + "[OUTPUT TRUNCATED]"
    )


# ============================================================
# DETECT TEST COMMAND
# ============================================================

def detect_test_command(repo_path: Path):
    """
    Detect a safe, known test command from repository files.

    Supported currently:

    Python / pytest
    Node / npm test
    Go
    Maven
    Gradle
    """

    # --------------------------------------------------------
    # Python / pytest via pyproject.toml
    # --------------------------------------------------------

    pyproject = repo_path / "pyproject.toml"

    if pyproject.exists():

        try:

            content = pyproject.read_text(
                encoding="utf-8",
                errors="ignore"
            ).lower()

            if "pytest" in content:

                return {
                    "detected": True,
                    "framework": "pytest",
                    "command": [
                        "python",
                        "-m",
                        "pytest",
                        "-q"
                    ]
                }

        except Exception:
            pass

    # --------------------------------------------------------
    # Python / pytest.ini
    # --------------------------------------------------------

    pytest_ini = repo_path / "pytest.ini"

    if pytest_ini.exists():

        return {
            "detected": True,
            "framework": "pytest",
            "command": [
                "python",
                "-m",
                "pytest",
                "-q"
            ]
        }

    # --------------------------------------------------------
    # Python / setup.cfg
    # --------------------------------------------------------

    setup_cfg = repo_path / "setup.cfg"

    if setup_cfg.exists():

        try:

            content = setup_cfg.read_text(
                encoding="utf-8",
                errors="ignore"
            ).lower()

            if "pytest" in content:

                return {
                    "detected": True,
                    "framework": "pytest",
                    "command": [
                        "python",
                        "-m",
                        "pytest",
                        "-q"
                    ]
                }

        except Exception:
            pass

    # --------------------------------------------------------
    # Node / package.json
    # --------------------------------------------------------

    package_json = repo_path / "package.json"

    if package_json.exists():

        try:

            with open(
                package_json,
                "r",
                encoding="utf-8"
            ) as f:

                package_data = json.load(f)

            scripts = package_data.get(
                "scripts",
                {}
            )

            if "test" in scripts:

                return {
                    "detected": True,
                    "framework": "npm",
                    "command": [
                        "npm",
                        "test"
                    ]
                }

        except Exception:
            pass

    # --------------------------------------------------------
    # Go
    # --------------------------------------------------------

    if any(
        repo_path.glob("*_test.go")
    ):

        return {
            "detected": True,
            "framework": "go",
            "command": [
                "go",
                "test",
                "./..."
            ]
        }

    # --------------------------------------------------------
    # Maven
    # --------------------------------------------------------

    if (repo_path / "pom.xml").exists():

        return {
            "detected": True,
            "framework": "maven",
            "command": [
                "mvn",
                "test"
            ]
        }

    # --------------------------------------------------------
    # Gradle wrapper
    # --------------------------------------------------------

    if (repo_path / "gradlew").exists():

        return {
            "detected": True,
            "framework": "gradle",
            "command": [
                "./gradlew",
                "test"
            ]
        }

    # --------------------------------------------------------
    # Gradle installed globally
    # --------------------------------------------------------

    if (repo_path / "build.gradle").exists():

        return {
            "detected": True,
            "framework": "gradle",
            "command": [
                "gradle",
                "test"
            ]
        }

    # --------------------------------------------------------
    # Nothing detected
    # --------------------------------------------------------

    return {
        "detected": False,
        "framework": None,
        "command": None
    }


# ============================================================
# RUN TEST COMMAND
# ============================================================

def run_test_command(
    repo_path: Path,
    command: list[str],
    timeout_seconds: int
):
    """
    Execute a known test command inside the repository.

    Security properties:

    - shell=False
    - working directory restricted to repository
    - timeout enforced
    - stdout/stderr captured
    """

    if timeout_seconds <= 0:

        raise ValueError(
            "timeout_seconds must be greater than 0."
        )

    if timeout_seconds > MAX_TEST_TIMEOUT:

        timeout_seconds = MAX_TEST_TIMEOUT

    start_time = time.perf_counter()

    try:

        result = subprocess.run(
            command,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False
        )

        duration = (
            time.perf_counter()
            - start_time
        )

        return {
            "executed": True,

            "passed":
                result.returncode == 0,

            "timed_out":
                False,

            "exit_code":
                result.returncode,

            "command":
                command,

            "stdout":
                limit_output(
                    result.stdout
                ),

            "stderr":
                limit_output(
                    result.stderr
                ),

            "duration_seconds":
                round(
                    duration,
                    2
                )
        }

    except subprocess.TimeoutExpired as e:

        duration = (
            time.perf_counter()
            - start_time
        )

        stdout = e.stdout or ""

        stderr = e.stderr or ""

        if isinstance(
            stdout,
            bytes
        ):

            stdout = stdout.decode(
                "utf-8",
                errors="replace"
            )

        if isinstance(
            stderr,
            bytes
        ):

            stderr = stderr.decode(
                "utf-8",
                errors="replace"
            )

        return {
            "executed": True,

            "passed": False,

            "timed_out": True,

            "exit_code": None,

            "command": command,

            "stdout":
                limit_output(
                    stdout
                ),

            "stderr":
                limit_output(
                    stderr
                ),

            "duration_seconds":
                round(
                    duration,
                    2
                ),

            "error": (
                f"Tests exceeded the "
                f"{timeout_seconds} second timeout."
            )
        }

    except FileNotFoundError:

        duration = (
            time.perf_counter()
            - start_time
        )

        return {
            "executed": False,

            "passed": False,

            "timed_out": False,

            "exit_code": None,

            "command": command,

            "stdout": "",

            "stderr": "",

            "duration_seconds":
                round(
                    duration,
                    2
                ),

            "error": (
                f"Test command not found: "
                f"{command[0]}"
            )
        }

    except Exception as e:

        duration = (
            time.perf_counter()
            - start_time
        )

        return {
            "executed": False,

            "passed": False,

            "timed_out": False,

            "exit_code": None,

            "command": command,

            "stdout": "",

            "stderr": "",

            "duration_seconds":
                round(
                    duration,
                    2
                ),

            "error": str(e)
        }


# ============================================================
# DIAGNOSE TEST FAILURE
# ============================================================

def diagnose_test_failure(
    repo_path: Path,
    test_result: dict,
    chunks: list,
    top_k: int = 5
):
    """
    Use Gemini to diagnose a failed test.

    Gemini receives:

    1. Test command
    2. Exit code
    3. stdout
    4. stderr
    5. Relevant repository chunks
    """

    failure_text = "\n".join([
        "TEST COMMAND:",
        " ".join(
            test_result.get(
                "command",
                []
            )
        ),

        "",

        f"EXIT CODE: "
        f"{test_result.get('exit_code')}",

        "",

        "STDOUT:",

        test_result.get(
            "stdout",
            ""
        ),

        "",

        "STDERR:",

        test_result.get(
            "stderr",
            ""
        )
    ])

    # --------------------------------------------------------
    # Search repository chunks using test failure output
    # --------------------------------------------------------

    combined_failure = (
        test_result.get(
            "stdout",
            ""
        )
        + "\n"
        + test_result.get(
            "stderr",
            ""
        )
    )

    failure_lower = combined_failure.lower()

    query_words = failure_lower.split()

    results = []

    for chunk in chunks:

        searchable_text = " ".join([
            str(chunk.get("name", "")),
            str(chunk.get("type", "")),
            str(chunk.get("file", "")),
            str(chunk.get("content", "")),
            " ".join(
                chunk.get(
                    "imports",
                    []
                )
            ),
            " ".join(
                chunk.get(
                    "references",
                    []
                )
            )
        ]).lower()

        matched_words = [
            word
            for word in query_words
            if len(word) >= 3
            and word in searchable_text
        ]

        if not matched_words:
            continue

        score = len(
            set(
                matched_words
            )
        )

        name = str(
            chunk.get(
                "name",
                ""
            )
        ).lower()

        file_path = str(
            chunk.get(
                "file",
                ""
            )
        ).lower()

        # ----------------------------------------------------
        # Strong signals from filenames/symbol names
        # ----------------------------------------------------

        if file_path in failure_lower:

            score += 10

        if name and name in failure_lower:

            score += 10

        results.append({
            "score": score,
            "chunk": chunk
        })

    results.sort(
        key=lambda result:
            result["score"],
        reverse=True
    )

    results = results[:top_k]

    context = build_context_from_chunks(
        results
    )

    prompt = f"""You are an AI Codebase Engineer
diagnosing a failed automated test.

Use ONLY the provided test output and repository
code context.

Do not invent files, functions, behavior, or errors
that are not supported by the evidence.

Your job is to determine the most likely cause of
the failure and explain what should be investigated.

Respond using exactly this structure:

FAILURE SUMMARY:
<brief description of what failed>

LIKELY CAUSE:
<best-supported explanation>

EVIDENCE:
<specific evidence from the test output and code,
with citations such as (file.py, lines 10-20)>

FILES / FUNCTIONS TO CHECK:
<short list and why>

RECOMMENDED NEXT STEP:
<what an engineer should investigate or change next>

CONFIDENCE:
<High / Medium / Low and why>

TEST OUTPUT:
{failure_text}

RELEVANT CODE:
{context}
"""

    response = call_gemini_with_retry(
        prompt
    )

    return {
        "diagnosis":
            response.text,

        "retrieved_chunks":
            len(results),

        "sources":
            sorted({
                result["chunk"]["file"]
                for result in results
            })
    }


# ============================================================
# DETECT TESTS ENDPOINT
# ============================================================
class DetectTestsRequest(BaseModel):
    repo_path: str


@app.post("/detect-tests")
def detect_tests(req: DetectTestsRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():
        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    if not repo_path.is_dir():
        return {
            "success": False,
            "error": "Repository path is not a directory."
        }

    # ---------------------------------------------------------
    # 1. Python / pytest
    # ---------------------------------------------------------

    pytest_indicators = [
        "pytest.ini",
        "pyproject.toml",
        "tox.ini",
        "setup.cfg",
    ]

    has_pytest_config = any(
        (repo_path / name).exists()
        for name in pytest_indicators
    )

    pytest_files = []

    for pattern in [
        "test_*.py",
        "*_test.py",
    ]:
        pytest_files.extend(
            repo_path.rglob(pattern)
        )

    if has_pytest_config or pytest_files:
        return {
            "success": True,
            "repository": str(repo_path),
            "detected": True,
            "framework": "pytest",
            "command": "pytest",
            "test_files": [
                str(p.relative_to(repo_path))
                for p in pytest_files
            ],
        }

    # ---------------------------------------------------------
    # 2. Node / npm
    # ---------------------------------------------------------

    package_json = repo_path / "package.json"

    if package_json.exists():

        try:
            with open(
                package_json,
                "r",
                encoding="utf-8"
            ) as f:
                package_data = json.load(f)

            scripts = package_data.get(
                "scripts",
                {}
            )

            if "test" in scripts:
                return {
                    "success": True,
                    "repository": str(repo_path),
                    "detected": True,
                    "framework": "npm",
                    "command": "npm test",
                }

        except Exception:
            pass

    # ---------------------------------------------------------
    # 3. Jupyter notebooks
    # ---------------------------------------------------------

    notebooks = list(
        repo_path.rglob("*.ipynb")
    )

    # Ignore Jupyter checkpoint files
    notebooks = [
        notebook
        for notebook in notebooks
        if ".ipynb_checkpoints" not in notebook.parts
    ]

    if notebooks:

        return {
            "success": True,
            "repository": str(repo_path),
            "detected": True,
            "framework": "jupyter",
            "command": (
                "jupyter nbconvert "
                "--execute "
                "--to notebook"
            ),
            "test_files": [
                str(
                    notebook.relative_to(repo_path)
                )
                for notebook in notebooks
            ],
        }

    # ---------------------------------------------------------
    # 4. Nothing detected
    # ---------------------------------------------------------

    return {
        "success": True,
        "repository": str(repo_path),
        "detected": False,
        "framework": None,
        "command": None,
    }

# ============================================================
# VALIDATE ENDPOINT
# ============================================================

class ValidateRequest(BaseModel):
    repo_path: str


def validate_jupyter_notebook(
    repo_path: Path,
    notebook_path: Path
):
    """
    Execute a Jupyter notebook against the repository.

    The original notebook is NEVER modified.

    A temporary executed copy is created and removed afterward.
    """

    try:

        from nbconvert.preprocessors import ExecutePreprocessor
        import nbformat

    except ImportError as e:

        return {
            "passed": False,
            "error": (
                "Jupyter validation dependencies are missing. "
                "Install with: pip install nbconvert nbclient jupyter"
            ),
            "details": str(e),
        }

    try:

        with open(
            notebook_path,
            "r",
            encoding="utf-8"
        ) as f:
            notebook = nbformat.read(
                f,
                as_version=4
            )

    except Exception as e:

        return {
            "passed": False,
            "error": "Could not read notebook.",
            "details": str(e),
        }

    # ---------------------------------------------------------
    # Execute in the repository root.
    #
    # This is important because notebooks often use paths like:
    #
    # data/file.csv
    #
    # ---------------------------------------------------------

    executor = ExecutePreprocessor(
        timeout=600,
        kernel_name="python3",
    )

    # Prevent matplotlib windows from appearing during validation.
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"

    old_env = os.environ.copy()

    try:

        os.environ.update(env)

        executor.preprocess(
            notebook,
            {
                "metadata": {
                    "path": str(repo_path)
                }
            }
        )

        return {
            "passed": True,
            "message": (
                "Notebook executed successfully."
            ),
        }

    except Exception as e:

        traceback_text = str(e)

        # nbconvert exceptions can contain a useful traceback
        # inside the exception text.
        return {
            "passed": False,
            "message": "Notebook execution failed.",
            "error": type(e).__name__,
            "traceback": traceback_text,
        }

    finally:

        os.environ.clear()
        os.environ.update(old_env)


@app.post("/validate")
def validate_repository(req: ValidateRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error": "Repository path doesn't exist."
        }

    if not repo_path.is_dir():

        return {
            "success": False,
            "error": "Repository path is not a directory."
        }

    # ---------------------------------------------------------
    # Detect the testing / validation framework
    # ---------------------------------------------------------

    detection = detect_tests(
        DetectTestsRequest(
            repo_path=str(repo_path)
        )
    )

    if not detection.get("detected"):

        return {
            "success": True,
            "validated": False,
            "passed": False,
            "message": (
                "No supported test framework was detected."
            ),
            "repository": str(repo_path),
        }

    framework = detection.get(
        "framework"
    )

    # ---------------------------------------------------------
    # JUPYTER
    # ---------------------------------------------------------

    if framework == "jupyter":

        test_files = detection.get(
            "test_files",
            []
        )

        results = []

        for relative_file in test_files:

            notebook_path = (
                repo_path / relative_file
            )

            result = validate_jupyter_notebook(
                repo_path,
                notebook_path
            )

            results.append({
                "file": relative_file,
                **result
            })

        all_passed = all(
            result.get("passed", False)
            for result in results
        )

        return {
            "success": True,
            "validated": True,
            "passed": all_passed,
            "framework": "jupyter",
            "repository": str(repo_path),
            "results": results,
        }

    # ---------------------------------------------------------
    # PYTEST
    # ---------------------------------------------------------

    if framework == "pytest":

        try:

            result = subprocess.run(
                [
                    "pytest",
                    "-q"
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=600,
            )

            return {
                "success": True,
                "validated": True,
                "passed": (
                    result.returncode == 0
                ),
                "framework": "pytest",
                "command": "pytest -q",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "repository": str(repo_path),
            }

        except subprocess.TimeoutExpired:

            return {
                "success": True,
                "validated": True,
                "passed": False,
                "framework": "pytest",
                "message": (
                    "Tests exceeded the 10 minute timeout."
                ),
                "repository": str(repo_path),
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }

    # ---------------------------------------------------------
    # NPM
    # ---------------------------------------------------------

    if framework == "npm":

        try:

            result = subprocess.run(
                [
                    "npm",
                    "test"
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=600,
            )

            return {
                "success": True,
                "validated": True,
                "passed": (
                    result.returncode == 0
                ),
                "framework": "npm",
                "command": "npm test",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "repository": str(repo_path),
            }

        except subprocess.TimeoutExpired:

            return {
                "success": True,
                "validated": True,
                "passed": False,
                "framework": "npm",
                "message": (
                    "Tests exceeded the 10 minute timeout."
                ),
                "repository": str(repo_path),
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }

    return {
        "success": False,
        "error": (
            f"Unsupported test framework: {framework}"
        ),
    }

    # --------------------------------------------------------
    # Detect test framework
    # --------------------------------------------------------

    detected = detect_test_command(
        repo_path
    )

    if not detected["detected"]:

        return {
            "success": True,
            "validated": False,
            "passed": False,
            "message": (
                "No supported test framework "
                "was detected."
            ),
            "repository":
                str(repo_path)
        }

    # --------------------------------------------------------
    # Get command
    # --------------------------------------------------------

    command = detected["command"]

    # --------------------------------------------------------
    # Run tests
    # --------------------------------------------------------

    test_result = run_test_command(
        repo_path=repo_path,
        command=command,
        timeout_seconds=req.timeout_seconds
    )

    # --------------------------------------------------------
    # Test execution itself failed
    #
    # Example:
    # pytest command not installed.
    # --------------------------------------------------------

    if not test_result["executed"]:

        return {
            "success": True,

            "validated": False,

            "passed": False,

            "framework":
                detected["framework"],

            "test_result":
                test_result,

            "ai_diagnosis":
                None
        }

    # --------------------------------------------------------
    # Tests passed
    #
    # IMPORTANT:
    # Do not spend a Gemini request on successful tests.
    # --------------------------------------------------------

    if test_result["passed"]:

        return {
            "success": True,

            "validated": True,

            "passed": True,

            "framework":
                detected["framework"],

            "test_result":
                test_result,

            "ai_diagnosis":
                None,

            "message":
                "All detected tests passed."
        }

    # --------------------------------------------------------
    # Tests failed
    #
    # Now we need repository chunks for Gemini diagnosis.
    # --------------------------------------------------------

    chunks_file = chunks_path_for(
        repo_path
    )

    if not chunks_file.exists():

        return {
            "success": True,

            "validated": True,

            "passed": False,

            "framework":
                detected["framework"],

            "test_result":
                test_result,

            "ai_diagnosis":
                None,

            "diagnosis_error": (
                "Tests failed, but chunks.json "
                "was not found. Run /chunk first."
            )
        }

    # --------------------------------------------------------
    # Load chunks
    # --------------------------------------------------------

    try:

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        chunks = data.get(
            "chunks",
            []
        )

    except json.JSONDecodeError:

        return {
            "success": True,

            "validated": True,

            "passed": False,

            "framework":
                detected["framework"],

            "test_result":
                test_result,

            "ai_diagnosis":
                None,

            "diagnosis_error": (
                "Tests failed, but chunks.json "
                "contains invalid JSON."
            )
        }

    # --------------------------------------------------------
    # Ask Gemini to diagnose failure
    # --------------------------------------------------------

    try:

        diagnosis = diagnose_test_failure(
            repo_path=repo_path,

            test_result=test_result,

            chunks=chunks,

            top_k=req.top_k
        )

    except Exception as e:

        return {
            "success": True,

            "validated": True,

            "passed": False,

            "framework":
                detected["framework"],

            "test_result":
                test_result,

            "ai_diagnosis":
                None,

            "diagnosis_error":
                f"AI diagnosis failed: {e}"
        }

    # --------------------------------------------------------
    # Final validation response
    # --------------------------------------------------------

    return {
        "success": True,

        "validated": True,

        "passed": False,

        "framework":
            detected["framework"],

        "test_result":
            test_result,

        "ai_diagnosis":
            diagnosis["diagnosis"],

        "diagnosis_retrieved_chunks":
            diagnosis[
                "retrieved_chunks"
            ],

        "diagnosis_sources":
            diagnosis[
                "sources"
            ],

        "model":
            GEMINI_MODEL
    }