from pathlib import Path
from dotenv import load_dotenv
from google import genai

import ast
import difflib
import json
import os
import shutil
import stat
import subprocess
import time


# ============================================================
# PATHS / CONFIGURATION
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

WORKSPACE_DIR = BACKEND_DIR / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PROPOSED_CHANGES_DIR = BACKEND_DIR / "proposed_changes"
PROPOSED_CHANGES_DIR.mkdir(exist_ok=True)


# ============================================================
# CONSTANTS
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
# GEMINI
# ============================================================

def call_gemini_with_retry(
    prompt: str,
    max_retries: int = 3
):
    """
    Call Gemini and retry temporary 503/unavailable errors.
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
# COMMON HELPERS
# ============================================================

def chunks_path_for(repo_path: Path) -> Path:
    return DATA_DIR / f"{repo_path.name}_chunks.json"


def validate_repo_path(repo_path: Path):
    """
    Validate that a repository path exists and is a directory.

    Returns:
        None when valid.
        Error string when invalid.
    """

    if not repo_path.exists():
        return "Repository path doesn't exist."

    if not repo_path.is_dir():
        return "Repository path is not a directory."

    return None


def load_chunks(repo_path: Path):
    """
    Load chunks.json for a repository.
    """

    chunks_file = chunks_path_for(repo_path)

    if not chunks_file.exists():
        raise FileNotFoundError(
            "chunks.json not found. Run /chunk first."
        )

    with open(
        chunks_file,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    return data.get("chunks", [])


def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


# ============================================================
# INGEST
# ============================================================

def ingest_repo(repo_url: str):

    repo_name = repo_url.rstrip("/").split("/")[-1]

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
            repo_url,
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

def analyze_repo(repo_path: Path):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
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

def chunk_repo(repo_path: Path):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
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

            # Current project chunks Python using AST.
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

                    if isinstance(node, ast.Import):

                        for alias in node.names:
                            imports.append(alias.name)

                    elif isinstance(node, ast.ImportFrom):

                        if node.module:
                            imports.append(
                                node.module
                            )

                imports = sorted(set(imports))

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

                    if isinstance(node, ast.ClassDef):
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

                        if isinstance(child, ast.Name):
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
        "success": True,
        "repository": str(repo_path),
        "files_processed": files_processed,
        "files_skipped": files_skipped,
        "total_chunks": len(all_chunks),
        "chunks_file": str(chunks_file),
        "chunks": all_chunks
    }


# ============================================================
# SHARED RETRIEVAL ENGINE
# ============================================================

def score_chunks(
    chunks,
    query: str,
    top_k: int = 5
):
    """
    Shared retrieval/scoring implementation.

    This replaces the duplicated scoring logic previously found
    in /retrieve, /context, /prompt, /ask, /investigate and /plan.
    """

    query = query.strip().lower()

    if not query:
        return []

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

        # Exact / partial name matches.
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

        # File matches.
        if query in file_path:
            score += 10

        file_matches = sum(
            1
            for word in query_words
            if word in file_path
        )

        score += file_matches * 4

        # References.
        reference_matches = sum(
            1
            for word in query_words
            if word in references
        )

        score += reference_matches * 5

        # Imports.
        import_matches = sum(
            1
            for word in query_words
            if word in imports
        )

        score += import_matches * 3

        # Content.
        content_matches = sum(
            1
            for word in query_words
            if word in content
        )

        score += content_matches

        # Prefer executable units slightly.
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

        # Penalize enormous chunks.
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

    return results[:top_k]


# ============================================================
# CONTEXT
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
            "No relevant code was found for this question."
        )

    return "\n---\n".join(context_parts)


def retrieve_chunks(
    repo_path: Path,
    query: str,
    top_k: int
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    if not query.strip():
        return {
            "success": False,
            "error": "Query cannot be empty."
        }

    try:
        chunks = load_chunks(repo_path)

        results = score_chunks(
            chunks,
            query,
            top_k
        )

        return {
            "success": True,
            "query": query,
            "match_count": len(results),
            "results": results
        }

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
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


def build_context(
    repo_path: Path,
    query: str,
    top_k: int
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    if not query.strip():
        return {
            "success": False,
            "error": "Query cannot be empty."
        }

    try:

        chunks = load_chunks(repo_path)

        results = score_chunks(
            chunks,
            query,
            top_k
        )

        context = build_context_from_chunks(
            results
        )

        return {
            "success": True,
            "query": query,
            "chunk_count": len(results),
            "context": context
        }

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
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

def build_prompt(
    repo_path: Path,
    question: str,
    top_k: int
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    question = question.strip()

    if not question:
        return {
            "success": False,
            "error": "Question cannot be empty."
        }

    try:

        chunks = load_chunks(repo_path)

        results = score_chunks(
            chunks,
            question,
            top_k
        )

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

        return {
            "success": True,
            "question": question,
            "retrieved_chunks": len(results),
            "prompt": prompt
        }

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
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

def ask_codebase(
    repo_path: Path,
    question: str,
    top_k: int
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    question = question.strip()

    if not question:
        return {
            "success": False,
            "error": "Question cannot be empty."
        }

    try:

        chunks = load_chunks(repo_path)

        results = score_chunks(
            chunks,
            question,
            top_k
        )

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

        response = call_gemini_with_retry(prompt)

        answer = response.text

        sources = [
            result["chunk"]["file"]
            for result in results
        ]

        return {
            "success": True,
            "question": question,
            "answer": answer,
            "retrieved_chunks": len(results),
            "model": GEMINI_MODEL,
            "sources": sorted(set(sources))
        }

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
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
# RELATIONSHIPS
# ============================================================

def get_relationships(
    repo_path: Path,
    target_name: str
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    target_name = target_name.strip()

    if not target_name:
        return {
            "success": False,
            "error": "Name cannot be empty."
        }

    try:
        chunks = load_chunks(repo_path)

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
        }

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

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
                chunk.get("references", [])
            )

            depends_on.update(
                chunk.get("imports", [])
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
        "depends_on": sorted(depends_on),
        "used_by": used_by,
        "imported_in_files": imported_in_files,
    }


# ============================================================
# INVESTIGATION
# ============================================================

def investigate_bug(
    repo_path: Path,
    bug_description: str,
    top_k: int
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    bug_description = bug_description.strip()

    if not bug_description:
        return {
            "success": False,
            "error": "bug_description cannot be empty."
        }

    try:

        chunks = load_chunks(repo_path)

        results = score_chunks(
            chunks,
            bug_description,
            top_k
        )

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
        }

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

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
            if (
                c.get("name") != name
                and name in c.get(
                    "references",
                    []
                )
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
        else (
            "No cross-references found among "
            "the retrieved code."
        )
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
# FEATURE PLANNING
# ============================================================

def plan_feature(
    repo_path: Path,
    feature_request: str,
    top_k: int
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    feature_request = feature_request.strip()

    if not feature_request:
        return {
            "success": False,
            "error": "feature_request cannot be empty."
        }

    try:

        chunks = load_chunks(repo_path)

        results = score_chunks(
            chunks,
            feature_request,
            top_k
        )

    except FileNotFoundError as e:

        return {
            "success": False,
            "error": str(e)
        }

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "chunks.json contains invalid JSON."
        }

    if not results:

        return {
            "success": True,
            "feature_request": feature_request,
            "plan": (
                "No closely related existing code was found for "
                "this feature request. This may mean it's a "
                "genuinely new capability with little to build on, "
                "or that it needs to be described using terms "
                "closer to the actual code."
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
            if (
                c.get("name") != name
                and name in c.get(
                    "references",
                    []
                )
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
        else (
            "No cross-references found among "
            "the retrieved code."
        )
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
    Remove a single markdown code fence if Gemini adds one.
    """

    check = text.strip()

    if check.startswith("```"):

        lines = check.split("\n")

        lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        return "\n".join(lines) + "\n"

    return text


def propose_change(
    repo_path: Path,
    file_path: str,
    instruction: str
):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    instruction = instruction.strip()

    if not instruction:
        return {
            "success": False,
            "error": "instruction cannot be empty."
        }

    repo_path_resolved = repo_path.resolve()

    target_file = (
        repo_path / file_path
    ).resolve()

    # Security check.
    try:

        target_file.relative_to(
            repo_path_resolved
        )

    except ValueError:

        return {
            "success": False,
            "error": (
                "file_path escapes the repository "
                "folder — refusing."
            )
        }

    if not target_file.exists():

        return {
            "success": False,
            "error": f"File not found: {file_path}"
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

FILE: {file_path}

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
            fromfile=f"{file_path} (current)",
            tofile=f"{file_path} (proposed)",
        )
    )

    diff_text = "".join(diff_lines)

    if not diff_text.strip():

        return {
            "success": True,
            "file_path": file_path,
            "instruction": instruction,
            "changed": False,
            "message": (
                "The model did not propose any "
                "change to this file."
            ),
            "diff": "",
        }

    safe_name = (
        file_path
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
        "file_path": file_path,
        "instruction": instruction,
        "changed": True,
        "diff": diff_text,
        "proposed_file_saved_to": str(
            proposal_file
        ),
        "model": GEMINI_MODEL,
    }


# ============================================================
# DAY 12 — TEST DETECTION
# ============================================================

def detect_tests(repo_path: Path):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    # --------------------------------------------------------
    # Python / pytest
    # --------------------------------------------------------

    pytest_files = []

    for root, dirs, files in os.walk(repo_path):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORE_DIRS
        ]

        for filename in files:

            lower_name = filename.lower()

            if (
                lower_name.startswith("test_")
                and lower_name.endswith(".py")
            ) or (
                lower_name.endswith("_test.py")
            ):

                pytest_files.append(
                    str(
                        Path(root)
                        .joinpath(filename)
                        .relative_to(repo_path)
                    )
                )

    if pytest_files:

        return {
            "success": True,
            "repository": str(repo_path),
            "detected": True,
            "framework": "pytest",
            "command": "pytest",
            "test_files": sorted(pytest_files)
        }

    # --------------------------------------------------------
    # package.json / npm
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
                    "success": True,
                    "repository": str(repo_path),
                    "detected": True,
                    "framework": "npm",
                    "command": "npm test"
                }

        except Exception:
            pass

    # --------------------------------------------------------
    # unittest
    # --------------------------------------------------------

    unittest_files = []

    for root, dirs, files in os.walk(repo_path):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORE_DIRS
        ]

        for filename in files:

            if (
                filename.endswith(".py")
                and (
                    filename.startswith("test")
                    or filename.endswith("_test.py")
                )
            ):

                unittest_files.append(filename)

    if unittest_files:

        return {
            "success": True,
            "repository": str(repo_path),
            "detected": True,
            "framework": "python-tests",
            "command": "python -m unittest discover"
        }

    return {
        "success": True,
        "repository": str(repo_path),
        "detected": False,
        "framework": None,
        "command": None
    }


# ============================================================
# DAY 12 — VALIDATION
# ============================================================

def validate_repository(repo_path: Path):

    error = validate_repo_path(repo_path)

    if error:
        return {
            "success": False,
            "error": error
        }

    detection = detect_tests(repo_path)

    if not detection.get("detected"):

        return {
            "success": True,
            "validated": False,
            "passed": False,
            "message": (
                "No supported test framework was detected."
            ),
            "repository": str(repo_path)
        }

    command = detection.get("command")

    try:

        completed = subprocess.run(
            command,
            cwd=str(repo_path),
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )

        passed = completed.returncode == 0

        return {
            "success": True,
            "validated": True,
            "passed": passed,
            "framework": detection.get(
                "framework"
            ),
            "command": command,
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "repository": str(repo_path)
        }

    except subprocess.TimeoutExpired as e:

        return {
            "success": True,
            "validated": True,
            "passed": False,
            "framework": detection.get(
                "framework"
            ),
            "command": command,
            "error": (
                "Test execution timed out "
                "after 300 seconds."
            ),
            "stdout": e.stdout,
            "stderr": e.stderr,
            "repository": str(repo_path)
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }