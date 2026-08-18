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

app = FastAPI(
    title="AI Codebase Engineer"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_DIR = BACKEND_DIR / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

# Chunks live here, NOT inside workspace/ — /ingest deletes and re-clones
# repo folders on every run, which would silently wipe chunks.json if it
# lived alongside the cloned code.
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def chunks_path_for(repo_path: Path) -> Path:
    return DATA_DIR / f"{repo_path.name}_chunks.json"


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


@app.post("/prompt")
def build_prompt(req: PromptRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

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
- When you reference code, cite it inline like (file.py, lines 10-15).
- Clearly separate what the code shows (evidence) from anything you are inferring.
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


@app.post("/ask")
def ask_codebase(req: AskRequest):

    repo_path = Path(req.repo_path)

    if not repo_path.exists():

        return {
            "success": False,
            "error":
                "Repository path doesn't exist."
        }

    chunks_file = chunks_path_for(repo_path)

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

        context = build_context_from_chunks(results)

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

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
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
            "error": str(e)
        }


# ============================================================
# RELATIONSHIPS (Day 8) — "where is this used?" / "what does
# this depend on?" — answered entirely from data /chunk already
# collected (imports + references per chunk). No new parsing.
# ============================================================

class RelationshipsRequest(BaseModel):
    repo_path: str
    name: str


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
        with open(chunks_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

    chunks = data.get("chunks", [])

    # Where is target_name DEFINED? (there could be more than one,
    # e.g. same function name in different files)
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

    # What does target_name's own code reference/import?
    # (its "depends on" list)
    depends_on = set()
    for chunk in chunks:
        if chunk.get("name") == target_name:
            depends_on.update(chunk.get("references", []))
            depends_on.update(chunk.get("imports", []))

    # Which OTHER functions/classes reference target_name?
    # (its "used by" list — the reverse direction)
    used_by = []
    for chunk in chunks:
        if chunk.get("name") == target_name:
            continue
        if target_name in chunk.get("references", []):
            used_by.append({
                "name": chunk.get("name"),
                "file": chunk.get("file"),
                "type": chunk.get("type"),
                "start_line": chunk.get("start_line"),
                "end_line": chunk.get("end_line"),
            })

    # Which files import target_name as a module?
    imported_in_files = sorted({
        chunk.get("file")
        for chunk in chunks
        if target_name in chunk.get("imports", [])
    })

    return {
        "success": True,
        "name": target_name,
        "defined_at": defined_at,
        "depends_on": sorted(depends_on),
        "used_by": used_by,
        "imported_in_files": imported_in_files,
    }


# ============================================================
# INVESTIGATE (Day 9) — turn a bug description into a structured
# investigation. Combines /retrieve's approach (find relevant code)
# with /relationships' data (what else touches that code), then
# asks the model to reason about a likely cause, not just answer
# a factual question.
# ============================================================

class InvestigateRequest(BaseModel):
    repo_path: str
    bug_description: str
    top_k: int = 5


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
        with open(chunks_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

    chunks = data.get("chunks", [])

    # ---- Step 1: retrieve relevant chunks ----
    query = bug_description.lower()
    query_words = query.split()

    results = []

    for chunk in chunks:
        searchable_text = " ".join([
            str(chunk.get("name", "")),
            str(chunk.get("type", "")),
            str(chunk.get("file", "")),
            str(chunk.get("content", "")),
            " ".join(chunk.get("imports", [])),
            " ".join(chunk.get("references", []))
        ]).lower()

        matched_words = [w for w in query_words if w in searchable_text]

        if not matched_words:
            continue

        score = len(matched_words)
        name = str(chunk.get("name", "")).lower()
        if query in name:
            score += 5
        content = str(chunk.get("content", "")).lower()
        if query in content:
            score += 3

        results.append({"score": score, "chunk": chunk})

    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:req.top_k]

    if not results:
        return {
            "success": True,
            "bug_description": bug_description,
            "investigation": (
                "No relevant code was found for this bug description. "
                "Try describing it with terms more likely to appear in the "
                "code (function names, error messages, feature names)."
            ),
            "retrieved_chunks": 0,
            "related_symbols": [],
            "sources": [],
        }

    # ---- Step 2: pull relationships for each retrieved chunk ----
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
            if c.get("name") != name and name in c.get("references", [])
        ]

        if used_by:
            related_notes.append(
                f"{name} (in {chunk.get('file')}) is used by: "
                f"{', '.join(sorted(set(used_by))[:5])}"
            )

    related_context = (
        "\n".join(related_notes)
        if related_notes
        else "No cross-references found among the retrieved code."
    )

    # ---- Step 3: build context + prompt ----
    context = build_context_from_chunks(results)

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
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        investigation = response.text
    except Exception as e:
        return {
            "success": False,
            "error": f"LLM call failed: {e}"
        }

    sources = sorted({result["chunk"]["file"] for result in results})

    return {
        "success": True,
        "bug_description": bug_description,
        "investigation": investigation,
        "retrieved_chunks": len(results),
        "related_symbols": sorted(related_symbol_names),
        "sources": sources,
        "model": GEMINI_MODEL,
    }