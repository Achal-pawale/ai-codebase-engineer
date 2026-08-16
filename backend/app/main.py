
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


# ============================================================
# ENVIRONMENT
# ============================================================

# .env is inside the backend folder
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Current stable Gemini model for this project
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
# FASTAPI
# ============================================================

app = FastAPI(
    title="AI Codebase Engineer"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE_DIR = BACKEND_DIR / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)


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


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "AI Codebase Engineer API is running."
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# ============================================================
# REMOVE READONLY FILES
# ============================================================

def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


# ============================================================
# INGEST
# ============================================================

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

            # Current AST chunking supports Python
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

                # ----------------------------------------
                # IMPORTS
                # ----------------------------------------

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

                # ----------------------------------------
                # FUNCTIONS / CLASSES
                # ----------------------------------------

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

                    # ----------------------------------------
                    # REFERENCES
                    # ----------------------------------------

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

    # ----------------------------------------
    # SAVE CHUNKS
    # ----------------------------------------

    chunks_file = repo_path / "chunks.json"

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

    chunks_file = repo_path / "chunks.json"

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
        # ----------------------------------------
        # Load chunks
        # ----------------------------------------

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        chunks = data.get("chunks", [])

        # ----------------------------------------
        # Prepare query
        # ----------------------------------------

        query_words = query.split()

        results = []

        # ----------------------------------------
        # Score every chunk
        # ----------------------------------------

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

            # ----------------------------------------
            # Relevance scoring
            # ----------------------------------------

            score = 0

            # 1. Exact name match
            if query == name:
                score += 20

            # 2. Query appears inside name
            elif query in name:
                score += 12

            # 3. Individual query words in name
            name_matches = sum(
                1
                for word in query_words
                if word in name
            )

            score += name_matches * 8

            # 4. Query appears in file path
            if query in file_path:
                score += 10

            # 5. Individual words in file path
            file_matches = sum(
                1
                for word in query_words
                if word in file_path
            )

            score += file_matches * 4

            # 6. References are more useful than
            # random occurrences in large code blocks
            reference_matches = sum(
                1
                for word in query_words
                if word in references
            )

            score += reference_matches * 5

            # 7. Imports
            import_matches = sum(
                1
                for word in query_words
                if word in imports
            )

            score += import_matches * 3

            # 8. Content matches
            content_matches = sum(
                1
                for word in query_words
                if word in content
            )

            score += content_matches

            # ----------------------------------------
            # Prefer focused structures
            # ----------------------------------------

            if chunk_type in {
                "function",
                "async_function"
            }:
                score += 2

            elif chunk_type == "class":
                score += 1

            # ----------------------------------------
            # Penalize huge chunks slightly
            # ----------------------------------------

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

            # ----------------------------------------
            # Save result
            # ----------------------------------------

            results.append({
                "score": score,
                "matched_words": matched_words,
                "chunk": chunk
            })

        # ----------------------------------------
        # Sort by relevance
        # ----------------------------------------

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

        # ----------------------------------------
        # Top K
        # ----------------------------------------

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


# `build_context_from_chunks()` helper


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
        return "No relevant code was found for this question."

    return "\n---\n".join(context_parts)


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

    chunks_file = repo_path / "chunks.json"

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
        # ----------------------------------------
        # Load persisted chunks
        # ----------------------------------------

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        chunks = data.get("chunks", [])

        # ----------------------------------------
        # Retrieve relevant chunks
        # ----------------------------------------

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

            # ----------------------------------------
            # Find matching query words
            # ----------------------------------------

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

            # ----------------------------------------
            # Relevance score
            # ----------------------------------------

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

            # Prefer focused structures
            if chunk_type in {
                "function",
                "async_function"
            }:
                score += 2

            elif chunk_type == "class":
                score += 1

            # Penalize extremely large chunks
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

        # ----------------------------------------
        # Sort by relevance
        # ----------------------------------------

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

        # ----------------------------------------
        # Select top K
        # ----------------------------------------

        results = results[:req.top_k]

        # ----------------------------------------
        # Build clean context
        # ----------------------------------------

        context_parts = []

        for result in results:

            chunk = result["chunk"]

            file_path = chunk.get(
                "file",
                ""
            )

            language = chunk.get(
                "language",
                ""
            )

            chunk_type = chunk.get(
                "type",
                ""
            )

            name = chunk.get(
                "name",
                ""
            )

            start_line = chunk.get(
                "start_line",
                ""
            )

            end_line = chunk.get(
                "end_line",
                ""
            )

            imports = chunk.get(
                "imports",
                []
            )

            references = chunk.get(
                "references",
                []
            )

            content = chunk.get(
                "content",
                ""
            )

            part = f"""FILE: {file_path}
LANGUAGE: {language}
TYPE: {chunk_type}
NAME: {name}
LINES: {start_line}-{end_line}

IMPORTS:
{", ".join(imports)}

REFERENCES:
{", ".join(references)}

CODE:
{content}
"""

            context_parts.append(part)

        context = "\n\n" + (
            "\n\n".join(context_parts)
        )

        # ----------------------------------------
        # Return context
        # ----------------------------------------

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
            "error":
                "Repository path doesn't exist."
        }

    chunks_file = repo_path / "chunks.json"

    if not chunks_file.exists():

        return {
            "success": False,
            "error":
                "chunks.json not found. Run /chunk first."
        }

    question = req.question.strip()

    if not question:

        return {
            "success": False,
            "error":
                "Question cannot be empty."
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

                "score":
                    score,

                "chunk":
                    chunk
            })

        results.sort(
            key=lambda result:
                result["score"],
            reverse=True
        )

        results = results[
            :req.top_k
        ]

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
- Explain the code clearly and concisely.

USER QUESTION:
{req.question}

CODEBASE CONTEXT:
{context}
"""

        return {

            "success":
                True,

            "question":
                req.question,

            "retrieved_chunks":
                len(results),

            "prompt":
                prompt
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
            "error": str(e)
        }


# ============================================================
# ASK GEMINI
# ============================================================

@app.post("/ask")
def ask_codebase(req: AskRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    chunks_file = repo_path / "chunks.json"

    if not chunks_file.exists():

        return {
            "success": False,
            "error":
                "chunks.json not found. Run /chunk first."
        }

    question = req.question.strip()

    if not question:

        return {
            "success": False,
            "error":
                "Question cannot be empty."
        }

    try:

        # ----------------------------------------
        # Load chunks
        # ----------------------------------------

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

        # ----------------------------------------
        # Retrieve relevant chunks
        # ----------------------------------------

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

                "score":
                    score,

                "chunk":
                    chunk
            })

        results.sort(
            key=lambda result:
                result["score"],
            reverse=True
        )

        results = results[
            :req.top_k
        ]

        # ----------------------------------------
        # Build context
        # ----------------------------------------

        context = build_context_from_chunks(results)

        # ----------------------------------------
        # Build prompt
        # ----------------------------------------

        prompt = f"""You are an AI Codebase Engineer.

Your job is to answer questions about a software
repository using the provided code context.

Rules:
- Use the provided code context as your primary source.
- Do not invent files, functions, classes, or behavior.
- If the context does not contain enough information,
  clearly say so.
- Mention relevant file names when useful.
- Explain the code clearly and concisely.

USER QUESTION:
{question}

CODEBASE CONTEXT:
{context}
"""

        # ----------------------------------------
        # Gemini
        # ----------------------------------------

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        answer = response.text

        # ----------------------------------------
        # Sources
        # ----------------------------------------

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
            "error": str(e)
        }
