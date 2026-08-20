import ast
import difflib
import json
import os
import shutil
import stat
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# ============================================================
# PATHS / CONFIG
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
# GENERAL HELPERS
# ============================================================

def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def chunks_path_for(repo_path: Path) -> Path:
    return DATA_DIR / f"{repo_path.name}_chunks.json"


def load_chunks(repo_path: Path):
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


# ============================================================
# RETRIEVAL
# ============================================================

def score_chunks(
    chunks,
    query: str,
    top_k: int = 5
):
    """
    Shared retrieval/scoring logic used by:
    retrieve, context, ask, investigate and plan.
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

        searchable_fields = [
            name,
            file_path,
            content,
            imports,
            references,
        ]

        matched_words = []

        for word in query_words:

            if any(
                word in field
                for field in searchable_fields
            ):
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

    return results[:top_k]


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


# ============================================================
# INGEST
# ============================================================

def ingest_repo(repo_url: str):

    repo_name = (
        repo_url
        .rstrip("/")
        .split("/")[-1]
    )

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

    if not repo_path.exists():
        return {
            "success": False,
            "error": "That path doesn't exist."
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

            directories.add(
                str(
                    current_root.relative_to(
                        repo_path
                    )
                )
            )

        for filename in files:

            file_path = current_root / filename

            if filename in important_names:

                important_files.append(
                    str(
                        file_path.relative_to(
                            repo_path
                        )
                    )
                )

            extension = (
                file_path.suffix.lower()
            )

            if extension in CODE_EXTENSIONS:

                relative_path = (
                    file_path.relative_to(
                        repo_path
                    )
                )

                files_info.append({
                    "path": str(relative_path),
                    "extension": extension,
                    "size_bytes":
                        file_path.stat().st_size
                })

                language_counts[
                    extension
                ] = (
                    language_counts.get(
                        extension,
                        0
                    ) + 1
                )

    return {
        "success": True,
        "summary": {
            "total_code_files":
                len(files_info),
            "language_counts":
                language_counts,
            "directory_count":
                len(directories),
            "important_files":
                sorted(important_files)
        },
        "directories":
            sorted(directories),
        "files":
            files_info
    }


# ============================================================
# CHUNK
# ============================================================

def chunk_repo(repo_path: Path):

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

            # Current AST chunker supports Python.
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

                relative_path = (
                    file_path.relative_to(
                        repo_path
                    )
                )

                imports = []

                for node in ast.walk(tree):

                    if isinstance(
                        node,
                        ast.Import
                    ):

                        for alias in node.names:
                            imports.append(
                                alias.name
                            )

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
                            start_line - 1:
                            end_line
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
                        structure_type = (
                            "async_function"
                        )

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
        "success": True,
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

def retrieve_chunks(
    repo_path: Path,
    query: str,
    top_k: int = 5
):

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


# ============================================================
# CONTEXT
# ============================================================

def build_context(
    repo_path: Path,
    query: str,
    top_k: int = 5
):

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


# ============================================================
# ASK
# ============================================================

def ask_codebase(
    repo_path: Path,
    question: str,
    top_k: int = 5
):

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
- When you reference code, cite it inline like
  (file.py, lines 10-15).
- Clearly separate what the code shows from anything
  you are inferring.
- Explain the code clearly and concisely.

USER QUESTION:
{question}

CODEBASE CONTEXT:
{context}
"""

    response = call_gemini_with_retry(
        prompt
    )

    sources = [
        result["chunk"]["file"]
        for result in results
    ]

    return {
        "success": True,
        "question": question,
        "answer": response.text,
        "retrieved_chunks":
            len(results),
        "model":
            GEMINI_MODEL,
        "sources":
            sorted(set(sources))
    }


# ============================================================
# RELATIONSHIPS
# ============================================================

def get_relationships(
    repo_path: Path,
    target_name: str
):

    chunks = load_chunks(repo_path)

    defined_at = [
        {
            "file":
                chunk.get("file"),
            "type":
                chunk.get("type"),
            "start_line":
                chunk.get("start_line"),
            "end_line":
                chunk.get("end_line"),
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
                "name":
                    chunk.get("name"),
                "file":
                    chunk.get("file"),
                "type":
                    chunk.get("type"),
                "start_line":
                    chunk.get("start_line"),
                "end_line":
                    chunk.get("end_line"),
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
        "depends_on":
            sorted(depends_on),
        "used_by":
            used_by,
        "imported_in_files":
            imported_in_files,
    }


# ============================================================
# INVESTIGATE
# ============================================================

def investigate_bug(
    repo_path: Path,
    bug_description: str,
    top_k: int = 5
):

    chunks = load_chunks(repo_path)

    results = score_chunks(
        chunks,
        bug_description,
        top_k
    )

    if not results:

        return {
            "success": True,
            "bug_description":
                bug_description,
            "investigation":
                (
                    "No relevant code was found "
                    "for this bug description."
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

        if not name:
            continue

        if name in related_symbol_names:
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
                f"{name} "
                f"(in {chunk.get('file')}) "
                f"is used by: "
                f"{', '.join(sorted(set(used_by))[:5])}"
            )

    related_context = (
        "\n".join(related_notes)
        if related_notes
        else
        "No cross-references found."
    )

    context = build_context_from_chunks(
        results
    )

    prompt = f"""You are an AI Codebase Engineer investigating a reported bug.

Use ONLY the code shown below.

Do not invent files, functions, or behavior that
isn't shown.

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

CROSS-REFERENCES:
{related_context}
"""

    response = call_gemini_with_retry(
        prompt
    )

    sources = sorted({
        result["chunk"]["file"]
        for result in results
    })

    return {
        "success": True,
        "bug_description":
            bug_description,
        "investigation":
            response.text,
        "retrieved_chunks":
            len(results),
        "related_symbols":
            sorted(
                related_symbol_names
            ),
        "sources":
            sources,
        "model":
            GEMINI_MODEL,
    }


# ============================================================
# PLAN
# ============================================================

def plan_feature(
    repo_path: Path,
    feature_request: str,
    top_k: int = 5
):

    chunks = load_chunks(repo_path)

    results = score_chunks(
        chunks,
        feature_request,
        top_k
    )

    if not results:

        return {
            "success": True,
            "feature_request":
                feature_request,
            "plan":
                (
                    "No closely related existing "
                    "code was found."
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

        if not name:
            continue

        if name in related_symbol_names:
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
                f"{name} "
                f"(in {chunk.get('file')}) "
                f"is used by: "
                f"{', '.join(sorted(set(used_by))[:5])}"
            )

    related_context = (
        "\n".join(related_notes)
        if related_notes
        else
        "No cross-references found."
    )

    context = build_context_from_chunks(
        results
    )

    prompt = f"""You are an AI Codebase Engineer planning a new feature
before any code is written.

Use ONLY the code shown below.

Do not invent files, functions, or behavior
that isn't shown.

Respond in exactly this structure:

AFFECTED FILES:
<files/functions this feature would likely touch, and why>

PROPOSED CHANGES:
<a concrete outline of what would need to change, cited inline like (file.py, lines X-Y)>

RISKS:
<what could break or edge cases to consider>

TESTS TO CONSIDER:
<what should be tested>

FEATURE REQUEST:
{feature_request}

RELEVANT EXISTING CODE:
{context}

CROSS-REFERENCES:
{related_context}
"""

    response = call_gemini_with_retry(
        prompt
    )

    sources = sorted({
        result["chunk"]["file"]
        for result in results
    })

    return {
        "success": True,
        "feature_request":
            feature_request,
        "plan":
            response.text,
        "retrieved_chunks":
            len(results),
        "related_symbols":
            sorted(
                related_symbol_names
            ),
        "sources":
            sources,
        "model":
            GEMINI_MODEL,
    }


# ============================================================
# PROPOSE CHANGE
# ============================================================

def strip_code_fence(text: str) -> str:

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

    repo_path_resolved = (
        repo_path.resolve()
    )

    target_file = (
        repo_path / file_path
    ).resolve()

    try:

        target_file.relative_to(
            repo_path_resolved
        )

    except ValueError:

        return {
            "success": False,
            "error":
                "file_path escapes the repository folder."
        }

    if not target_file.exists():

        return {
            "success": False,
            "error":
                f"File not found: {file_path}"
        }

    if not target_file.is_file():

        return {
            "success": False,
            "error":
                "file_path is not a file."
        }

    try:

        original_content = (
            target_file.read_text(
                encoding="utf-8"
            )
        )

    except UnicodeDecodeError:

        return {
            "success": False,
            "error":
                "This file is not readable text."
        }

    prompt = f"""You are an AI Codebase Engineer making a single, focused code change.

Output ONLY the complete updated file content.

Rules:
- Do not include markdown fences.
- Do not include explanations.
- Do not change unrelated code.
- Preserve formatting and comments.
- If the instruction cannot safely be applied,
  return the original content unchanged.

FILE:
{file_path}

INSTRUCTION:
{instruction}

CURRENT FILE CONTENT:
{original_content}
"""

    response = call_gemini_with_retry(
        prompt
    )

    proposed_content = strip_code_fence(
        response.text
    )

    diff_lines = list(
        difflib.unified_diff(
            original_content.splitlines(
                keepends=True
            ),
            proposed_content.splitlines(
                keepends=True
            ),
            fromfile=
                f"{file_path} (current)",
            tofile=
                f"{file_path} (proposed)",
        )
    )

    diff_text = "".join(
        diff_lines
    )

    if not diff_text.strip():

        return {
            "success": True,
            "file_path":
                file_path,
            "instruction":
                instruction,
            "changed":
                False,
            "message":
                "No change proposed.",
            "diff":
                "",
        }

    safe_name = (
        file_path
        .replace("/", "__")
        .replace("\\", "__")
    )

    proposal_file = (
        PROPOSED_CHANGES_DIR
        /
        f"{repo_path.name}__{safe_name}.proposed"
    )

    proposal_file.write_text(
        proposed_content,
        encoding="utf-8"
    )

    return {
        "success": True,
        "file_path":
            file_path,
        "instruction":
            instruction,
        "changed":
            True,
        "diff":
            diff_text,
        "proposed_file_saved_to":
            str(proposal_file),
        "model":
            GEMINI_MODEL,
    }


# ============================================================
# DAY 13 — END-TO-END ENGINEER WORKFLOW
# ============================================================

def engineer_workflow(
    repo_url: str,
    task_type: str,
    question: str,
    top_k: int = 5
):
    """
    Complete Day 13 pipeline.

    1. Clone repository
    2. Chunk repository
    3. Retrieve relevant code
    4. Ask / investigate / plan
    5. Return everything in one response
    """

    # --------------------------------------------------------
    # STEP 1 — INGEST
    # --------------------------------------------------------

    ingest_result = ingest_repo(
        repo_url
    )

    if not ingest_result.get("success"):

        return {
            "success": False,
            "stage": "ingest",
            "error":
                ingest_result.get(
                    "error",
                    "Repository ingestion failed."
                ),
            "ingest": ingest_result
        }

    repo_path = Path(
        ingest_result["cloned_to"]
    )

    # --------------------------------------------------------
    # STEP 2 — CHUNK
    # --------------------------------------------------------

    chunk_result = chunk_repo(
        repo_path
    )

    if not chunk_result.get("success"):

        return {
            "success": False,
            "stage": "chunk",
            "error":
                chunk_result.get(
                    "error",
                    "Repository chunking failed."
                ),
            "ingest": ingest_result,
            "chunk": chunk_result
        }

    # --------------------------------------------------------
    # STEP 3 — RUN THE REQUESTED AI OPERATION
    # --------------------------------------------------------

    if task_type == "ask":

        ai_result = ask_codebase(
            repo_path,
            question,
            top_k
        )

    elif task_type == "investigate":

        ai_result = investigate_bug(
            repo_path,
            question,
            top_k
        )

    elif task_type == "plan":

        ai_result = plan_feature(
            repo_path,
            question,
            top_k
        )

    else:

        return {
            "success": False,
            "stage": "task",
            "error":
                (
                    "task_type must be "
                    "'ask', 'investigate', "
                    "or 'plan'."
                ),
            "ingest": ingest_result,
            "chunk": {
                "success": True,
                "total_chunks":
                    chunk_result.get(
                        "total_chunks",
                        0
                    )
            }
        }

    # --------------------------------------------------------
    # STEP 4 — RETURN COMPLETE PIPELINE RESULT
    # --------------------------------------------------------

    return {
        "success": True,

        "workflow": [
            "ingest",
            "chunk",
            task_type
        ],

        "repository": {
            "url": repo_url,
            "path": str(repo_path)
        },

        "ingest": {
            "success":
                ingest_result.get(
                    "success"
                ),
            "file_count":
                ingest_result.get(
                    "file_count"
                ),
            "top_level_items":
                ingest_result.get(
                    "top_level_items"
                )
        },

        "chunk": {
            "success":
                chunk_result.get(
                    "success"
                ),
            "files_processed":
                chunk_result.get(
                    "files_processed"
                ),
            "files_skipped":
                chunk_result.get(
                    "files_skipped"
                ),
            "total_chunks":
                chunk_result.get(
                    "total_chunks"
                )
        },

        "task": {
            "type": task_type,
            "question": question,
            "top_k": top_k
        },

        "result": ai_result
    }