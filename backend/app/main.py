from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import subprocess
import shutil
import os
import stat
import ast
import json

app = FastAPI(title="AI Codebase Engineer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
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
IMPORTANT_FILES = {
    "README.md",
    "README",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
}


class AnalyzeRequest(BaseModel):
    cloned_to: str


@app.post("/analyze")
def analyze_repo(req: AnalyzeRequest):
    repo_path = Path(req.cloned_to)

    if not repo_path.exists():
        return {
            "success": False,
            "error": "That path doesn't exist. Ingest the repo first.",
        }

    files_info = []
    language_counts = {}
    directories = set()
    important_files = []

    for root, dirs, files in os.walk(repo_path):

        # Ignore directories we don't want to analyze
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        # Collect directory structure
        for directory in dirs:
            directory_path = Path(root) / directory
            relative_directory = directory_path.relative_to(repo_path)
            directories.add(str(relative_directory))

        # Analyze files
        for filename in files:
            file_path = Path(root) / filename
            ext = file_path.suffix

            if filename in IMPORTANT_FILES:
                 rel_path = file_path.relative_to(repo_path)
                 important_files.append(str(rel_path))

            if ext in CODE_EXTENSIONS:

                # Count files by extension
                language_counts[ext] = language_counts.get(ext, 0) + 1

                # Get relative path
                rel_path = file_path.relative_to(repo_path)

                # Get file size
                size = file_path.stat().st_size

                files_info.append({
                    "path": str(rel_path),
                    "extension": ext,
                    "size_bytes": size,
                })

    return {
    "success": True,
    "summary": {
        "total_code_files": len(files_info),
        "language_counts": language_counts,
        "directory_count": len(directories),
        "important_files": sorted(important_files),
    },
    "files": files_info,
}

class FileRequest(BaseModel):
    repo_path: str
    file_path: str


@app.post("/file")
def read_file(req: FileRequest):
    repo_path = Path(req.repo_path)
    file_path = repo_path / req.file_path

    if not repo_path.exists():
        return {
            "success": False,
            "error": "Repository path does not exist."
        }

    if not file_path.exists():
        return {
            "success": False,
            "error": "File does not exist."
        }

    if not file_path.is_file():
        return {
            "success": False,
            "error": "The provided path is not a file."
        }

    try:
        content = file_path.read_text(encoding="utf-8")

        return {
            "success": True,
            "path": req.file_path,
            "content": content,
        }

    except UnicodeDecodeError:
        return {
            "success": False,
            "error": "This file is not a readable text file."
        }

class SearchRequest(BaseModel):
    repo_path: str
    query: str


@app.post("/search")
def search_repo(req: SearchRequest):
    repo_path = Path(req.repo_path)

    if not repo_path.exists():
        return {
            "success": False,
            "error": "That repository path doesn't exist."
        }

    results = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            file_path = Path(root) / filename

            try:
                lines = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                ).splitlines()
            except Exception:
                continue

            matches = []

            for line_number, line in enumerate(lines, start=1):
                if req.query.lower() in line.lower():
                    matches.append({
                        "line": line_number,
                        "text": line.strip()
                    })

            if matches:
                results.append({
                  "path": str(file_path.relative_to(repo_path)),
                "matches": matches
    })

    return {
        "success": True,
        "query": req.query,
        "match_count": len(results),
        "matches": results
    }

class IngestRequest(BaseModel):
    repo_url: str


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

    dest = WORKSPACE_DIR / repo_name

    # Remove existing repository if it already exists
    if dest.exists():
        shutil.rmtree(dest, onerror=remove_readonly)

    # Clone repository
    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            req.repo_url,
            str(dest),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr,
        }

    # Get top-level items
    top_level = [
        item.name
        for item in dest.iterdir()
        if item.name not in IGNORE_DIRS
    ]

    # Count files
    file_count = 0

    for root, dirs, files in os.walk(dest):
        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS
        ]

        file_count += len(files)

    return {
        "success": True,
        "cloned_to": str(dest),
        "top_level_items": sorted(top_level),
        "file_count": file_count,
    }

@app.post("/dependencies")
def get_dependencies(req: AnalyzeRequest):
    repo_path = Path(req.cloned_to)

    if not repo_path.exists():
        return {
            "success": False,
            "error": "That repository path doesn't exist."
        }

    dependency_files = {
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "Pipfile": "Python",
        "package.json": "Node.js",
        "pom.xml": "Java",
        "go.mod": "Go",
        "Gemfile": "Ruby",
    }

    found = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            if filename in dependency_files:
                file_path = Path(root) / filename

                found.append({
                    "file": str(file_path.relative_to(repo_path)),
                    "language": dependency_files[filename]
                })

    return {
        "success": True,
        "dependency_files": found,
        "count": len(found)
    }

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

class AskRequest(BaseModel):
    repo_path: str
    question: str
    top_k: int = 5


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
            d for d in dirs
            if d not in IGNORE_DIRS
        ]

        for filename in files:

            file_path = Path(root) / filename

            if file_path.suffix.lower() not in CODE_EXTENSIONS:
                files_skipped += 1
                continue

            # Structured AST chunking currently supports Python
            if file_path.suffix.lower() != ".py":
                files_skipped += 1
                continue

            try:
                content = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

                tree = ast.parse(content)
                lines = content.splitlines()

                relative_path = file_path.relative_to(repo_path)

                # -----------------------------
                # Extract imports
                # -----------------------------

                imports = []

                for node in ast.walk(tree):

                    if isinstance(node, ast.Import):

                        for alias in node.names:
                            imports.append(alias.name)

                    elif isinstance(node, ast.ImportFrom):

                        if node.module:
                            imports.append(node.module)

                imports = sorted(set(imports))

                # -----------------------------
                # Extract functions/classes
                # -----------------------------

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
                        lines[start_line - 1:end_line]
                    )

                    # Determine type
                    if isinstance(node, ast.ClassDef):
                        structure_type = "class"

                    elif isinstance(
                        node,
                        ast.AsyncFunctionDef
                    ):
                        structure_type = "async_function"

                    else:
                        structure_type = "function"

                    # -----------------------------
                    # Extract references
                    # -----------------------------

                    references = []

                    for child in ast.walk(node):

                        if isinstance(child, ast.Name):
                            references.append(child.id)

                        elif isinstance(child, ast.Attribute):
                            references.append(child.attr)

                    references = sorted(set(references))

                    all_chunks.append({
                        "chunk_id": len(all_chunks) + 1,
                        "type": structure_type,
                        "name": node.name,
                        "file": str(relative_path),
                        "language": "python",
                        "imports": imports,
                        "references": references,
                        "start_line": start_line,
                        "end_line": end_line,
                        "content": chunk_content
                    })

                files_processed += 1

            except SyntaxError:
                files_skipped += 1

            except Exception:
                files_skipped += 1

    # --------------------------------
    # Save chunks to disk
    # --------------------------------

    chunks_file = repo_path / "chunks.json"

    with open(
        chunks_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "repository": str(repo_path),
                "total_chunks": len(all_chunks),
                "chunks": all_chunks
            },
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------
    # Return result
    # --------------------------------

    return {
        "success": True,
        "repository": str(repo_path),
        "files_processed": files_processed,
        "files_skipped": files_skipped,
        "total_chunks": len(all_chunks),
        "chunks_file": str(chunks_file),
        "chunks": all_chunks
    }

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

    try:
        # Load persisted chunks
        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        chunks = data.get("chunks", [])

        query = req.query.strip().lower()

        if not query:
            return {
                "success": False,
                "error": "Query cannot be empty."
            }

        # Break query into individual words
        query_words = query.split()

        results = []

        for chunk in chunks:

            # Search across useful chunk information
            searchable_text = " ".join([
                str(chunk.get("name", "")),
                str(chunk.get("type", "")),
                str(chunk.get("file", "")),
                str(chunk.get("content", "")),
                " ".join(chunk.get("imports", [])),
                " ".join(chunk.get("references", []))
            ]).lower()

            # Count how many query words appear
            matched_words = []

            for word in query_words:
                if word in searchable_text:
                    matched_words.append(word)

            if not matched_words:
                continue

            # Simple relevance score
            score = len(matched_words)

            # Extra weight for function/class name
            name = str(chunk.get("name", "")).lower()

            if query in name:
                score += 5

            # Extra weight if query appears in content
            content = str(chunk.get("content", "")).lower()

            if query in content:
                score += 3

            results.append({
                "score": score,
                "matched_words": matched_words,
                "chunk": chunk
            })

        # Highest score first
        results.sort(
            key=lambda result: result["score"],
            reverse=True
        )

        # Return only top K results
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

@app.post("/context")
def build_context(req: ContextRequest):
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

    try:
        # -----------------------------
        # Load persisted chunks
        # -----------------------------

        with open(
            chunks_file,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        chunks = data.get("chunks", [])

        query = req.query.strip().lower()

        if not query:
            return {
                "success": False,
                "error": "Query cannot be empty."
            }

        # -----------------------------
        # Retrieve relevant chunks
        # -----------------------------

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

            matched_words = []

            for word in query_words:
                if word in searchable_text:
                    matched_words.append(word)

            if not matched_words:
                continue

            score = len(matched_words)

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

        # -----------------------------
        # Sort by relevance
        # -----------------------------

        results.sort(
            key=lambda result: result["score"],
            reverse=True
        )

        results = results[:req.top_k]

        # -----------------------------
        # Build context
        # -----------------------------

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

        context = "\n---\n".join(context_parts)

        # -----------------------------
        # Return context
        # -----------------------------

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

@app.post("/ask")
def ask_codebase(req: AskRequest):
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

    question = req.question.strip()

    if not question:
        return {
            "success": False,
            "error": "Question cannot be empty."
        }

    # --------------------------------
    # Load chunks
    # --------------------------------

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

    chunks = data.get("chunks", [])

    # --------------------------------
    # Retrieve relevant chunks
    # --------------------------------

    query = question.lower()
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

        matched_words = [
            word
            for word in query_words
            if word in searchable_text
        ]

        if not matched_words:
            continue

        score = len(matched_words)

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
        key=lambda result: result["score"],
        reverse=True
    )

    results = results[:req.top_k]

    # --------------------------------
    # Build context
    # --------------------------------

    context_parts = []

    for result in results:

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

    context = "\n---\n".join(context_parts)

    # --------------------------------
    # Temporary answer
    # --------------------------------

    if not results:
        answer = (
            "I couldn't find relevant code chunks "
            "for that question."
        )

    else:
        answer = (
            "Relevant code was found. "
            "The repository context has been prepared "
            "for an AI model."
        )

    return {
        "success": True,
        "question": req.question,
        "answer": answer,
        "retrieved_chunks": len(results),
        "context": context
    }