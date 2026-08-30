# AI Codebase Engineer

AI Codebase Engineer is an AI-powered software repository analysis and engineering assistant built with **FastAPI, Python, Git, AST-based code analysis, retrieval, and Google Gemini**.

The project is designed to help developers understand unfamiliar repositories, retrieve relevant source code, ask questions about a codebase, investigate bugs, plan changes, propose code modifications, and validate repositories through their existing test frameworks.

---

## Overview

Working with an unfamiliar codebase often requires manually navigating files, understanding functions and classes, tracing references, and identifying where changes should be made.

AI Codebase Engineer provides an automated workflow:

```text
GitHub Repository
       ↓
Repository Ingestion
       ↓
Code Analysis
       ↓
Python AST Chunking
       ↓
Code Retrieval
       ↓
AI Codebase Engineer
       ↓
Ask / Investigate / Plan
       ↓
Proposed Code Change
       ↓
Test Detection
       ↓
Validation
```

The backend performs the repository processing and AI operations, while the current frontend provides a minimal browser interface for checking backend connectivity.

---

## Features

### Repository Ingestion

Repositories can be cloned directly from GitHub using Git.

The backend:

* Accepts a GitHub repository URL
* Performs a shallow clone using `git clone --depth 1`
* Stores repositories inside the backend workspace
* Counts repository files
* Identifies top-level repository items
* Handles failed Git clone operations

---

### Repository Analysis

The analyzer walks through the cloned repository and extracts:

* Code files
* File extensions
* File sizes
* Language/file-extension counts
* Directory structure
* Important project files

Important files include files such as:

```text
README.md
requirements.txt
package.json
pyproject.toml
setup.py
Dockerfile
docker-compose.yml
.env.example
Makefile
```

---

### Python AST Code Chunking

Python source files are parsed using Python's built-in `ast` module.

The chunking system identifies:

* Functions
* Async functions
* Classes
* Function/class names
* File paths
* Programming language
* Imports
* Referenced symbols
* Start and end line numbers
* Source code content

The generated chunks are stored as JSON and are subsequently used by the retrieval and AI workflows.

---

### Code Retrieval

The system provides repository-aware code retrieval.

Given a query, the retrieval system scores available code chunks based on matching terms and returns the highest-ranked results.

Each result contains information such as:

```text
score
matched_words
chunk
```

The chunk can contain:

```text
file
type
name
language
imports
references
start_line
end_line
content
```

The retrieval system also supports a configurable `top_k` value.

---

### AI Codebase Questions

The `/ask` endpoint allows developers to ask questions about an indexed repository.

The backend:

1. Retrieves relevant code chunks
2. Builds code context
3. Sends the repository context to Google Gemini
4. Generates a codebase-grounded response
5. Returns the answer and source information

The system explicitly instructs the AI not to invent files, functions, classes, or behavior.

---

### Bug Investigation

The `/investigate` endpoint allows a developer to describe a problem in the repository.

The investigation workflow uses repository retrieval and Gemini to analyze the issue and return:

* Investigation
* Retrieved chunks
* Related symbols
* Source files
* AI model information

---

### Change Planning

The `/plan` endpoint accepts a feature request and generates an implementation plan based on the existing repository.

The response includes:

* Generated plan
* Retrieved repository context
* Related symbols
* Source files
* AI model information

---

### Proposed Code Changes

The `/propose-change` endpoint can generate a proposed modification to a specific file.

It accepts:

```text
repo_path
file_path
instruction
```

The backend reads the target file, sends the requested change together with the existing code to Gemini, and can save the proposed result under the backend's proposed-changes directory.

A unified diff is generated to show the modification.

---

### Dependency / Relationship Analysis

The `/relationships` endpoint analyzes relationships between indexed symbols.

The system can identify relationships such as:

```text
Depends on
Used by
```

For example:

```text
login_user
    ↓
validate_user

dashboard
    ↓
login_user
```

This provides a basic way of understanding how functions and symbols are connected within the repository.

---

### Test Detection

The backend automatically attempts to detect supported testing setups.

Currently supported detection includes:

* pytest
* Python test files
* npm test
* Maven
* Gradle

Examples of detected commands include:

```bash
python -m pytest
npm test
mvn test
gradle test
```

---

### Repository Validation

The `/validate` endpoint executes the detected test command.

The backend returns:

* Validation status
* Pass/fail status
* Test framework
* Command executed
* Process return code
* Standard output
* Standard error

Test execution has a timeout of **300 seconds**.

---

### Complete Engineering Workflow

The `/engineer` endpoint combines multiple operations into a single workflow:

```text
Repository Ingestion
        ↓
Code Chunking
        ↓
Ask / Investigate / Plan
```

Supported task types are:

```text
ask
investigate
plan
```

The endpoint reports the workflow stage if a failure occurs.

---

# Technology Stack

## Backend

* Python
* FastAPI
* Pydantic
* Uvicorn
* Python AST
* Git
* Google Gemini via `google-genai`
* SlowAPI
* pytest
* httpx

## Frontend

The frontend currently included in the project is intentionally minimal:

* HTML
* CSS
* Vanilla JavaScript
* Browser Fetch API

The current frontend provides a backend health-check interface.

---

# Project Structure

```text
ai-codebase-engineer/
│
├── backend/
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── services.py
│   │
│   ├── tests/
│   │   ├── test_engineer.py
│   │   ├── test_health.py
│   │   ├── test_relationships.py
│   │   └── test_retrieval.py
│   │
│   ├── proposed_changes/
│   │   └── backend__app__main.py.proposed
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .dockerignore
│
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── styles.css
│
├── .env
├── .gitignore
├── LEARNINGS.md
└── README.md
```

---

# Backend API

The FastAPI application exposes the following routes.

## Basic

### `GET /`

Returns basic API information.

### `GET /health`

Returns:

```json
{
  "status": "ok"
}
```

---

## Repository Processing

### `POST /ingest`

Request:

```json
{
  "repo_url": "https://github.com/user/repository"
}
```

Clones the repository and returns information about the cloned repository.

### `POST /analyze`

Request:

```json
{
  "cloned_to": "/path/to/repository"
}
```

Analyzes repository files, languages, directories, and important files.

### `POST /chunk`

Request:

```json
{
  "repo_path": "/path/to/repository"
}
```

Parses Python files and creates structured code chunks.

---

## Retrieval and Context

### `POST /retrieve`

Request:

```json
{
  "repo_path": "/path/to/repository",
  "query": "login authentication",
  "top_k": 5
}
```

Returns the most relevant indexed code chunks.

### `POST /context`

Builds repository context from retrieved chunks.

### `POST /prompt`

Builds a repository-grounded AI prompt from retrieved code.

---

## AI Operations

### `POST /ask`

Ask a question about the repository.

```json
{
  "repo_path": "/path/to/repository",
  "question": "How does authentication work?",
  "top_k": 5
}
```

### `POST /investigate`

Investigate a repository problem.

```json
{
  "repo_path": "/path/to/repository",
  "bug_description": "Users receive a 500 error during indexing.",
  "top_k": 5
}
```

### `POST /plan`

Generate an implementation plan.

```json
{
  "repo_path": "/path/to/repository",
  "feature_request": "Add logging around repository indexing.",
  "top_k": 5
}
```

### `POST /propose-change`

Generate a proposed modification for a specific file.

```json
{
  "repo_path": "/path/to/repository",
  "file_path": "backend/app/main.py",
  "instruction": "Add logging to the health endpoint."
}
```

---

## Relationships

### `POST /relationships`

Request:

```json
{
  "repo_path": "/path/to/repository",
  "name": "login_user"
}
```

Returns information about symbol relationships, including dependencies and usages.

---

## Testing

### `POST /detect-tests`

Detects a supported test framework.

### `POST /validate`

Runs the detected test framework and returns the execution result.

---

## Complete Workflow

### `POST /engineer`

Runs the repository engineering workflow.

Request:

```json
{
  "repo_url": "https://github.com/user/repository",
  "task_type": "ask",
  "question": "How does authentication work?",
  "top_k": 5
}
```

Supported `task_type` values:

```text
ask
investigate
plan
```

The workflow is:

```text
ingest
  ↓
chunk
  ↓
ask / investigate / plan
```

---

# API Rate Limiting

The backend uses **SlowAPI** for rate limiting.

The application has a default limit of:

```text
60 requests/minute
```

Individual routes also define more restrictive limits.

Examples include:

```text
/ingest       10/minute
/ask          10/minute
/investigate  10/minute
/plan         10/minute
/retrieve     30/minute
```

---

# CORS

The backend uses FastAPI's `CORSMiddleware`.

By default, the following frontend origins are allowed:

```text
http://localhost:3000
http://localhost:5173
```

Additional origins can be configured using:

```env
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

# Environment Variables

The backend uses environment variables for configuration.

The repository contains:

```text
.env
backend/.env.example
```

The Gemini API credential is intended to remain on the backend and should **never be placed in frontend JavaScript or committed to GitHub**.

The `.gitignore` excludes:

```text
.env
```

---

# Running the Backend

Create and activate a virtual environment:

```bash
python -m venv .venv
```

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Start FastAPI:

```bash
uvicorn app.main:app --reload --app-dir backend
```

The API will be available at:

```text
http://localhost:8000
```

Swagger documentation:

```text
http://localhost:8000/docs
```

---

# Running the Frontend

The frontend currently consists of static files.

From the `frontend` directory, serve the files using a local HTTP server.

For example:

```bash
cd frontend
python -m http.server 3000
```

Then open:

```text
http://localhost:3000
```

The current JavaScript frontend communicates with:

```text
http://localhost:8000/health
```

and displays the backend health status.

---

# Running Tests

The backend contains pytest tests.

Run:

```bash
pytest backend/tests
```

The existing tests cover areas including:

* Root and health endpoints
* Engineer request validation
* Invalid engineer task types
* Repository relationships
* Retrieval scoring
* `top_k` retrieval behavior

---

# Docker

The backend includes a Dockerfile:

```text
backend/Dockerfile
```

The backend is therefore structured to support containerized execution.

---

# Security

The project follows a backend-only approach for AI credentials.

Sensitive credentials should remain on the FastAPI server.

Do not place Gemini API credentials inside:

```text
frontend/
```

Do not commit `.env` files containing secrets.

The repository's `.gitignore` already excludes:

```text
.env
backend/workspace/
backend/data/
backend/proposed_changes/
```

---

# Current Frontend Status

The frontend contained in this repository is currently a minimal proof-of-concept interface.

It provides:

```text
AI Codebase Engineer
        ↓
Check backend status
        ↓
GET /health
```

The frontend uses:

```javascript
fetch("http://localhost:8000/health")
```

and displays whether the FastAPI backend can be reached.

The backend already contains the substantially larger repository engineering functionality described above.

---

# Current Limitations

The current implementation does not provide a complete graphical interface for every backend capability.

In particular, the existing frontend does not yet provide dedicated UI screens for:

* Repository ingestion
* Repository analysis
* Code chunk inspection
* Retrieval results
* AI questions
* Bug investigation
* Change planning
* Relationship exploration
* Proposed-change review
* Test execution visualization

These capabilities are implemented primarily in the FastAPI backend and its service layer.

---

# Development Direction

The existing backend provides a foundation for a richer developer interface.

A future frontend can expose the backend workflow as:

```text
Connect Repository
        ↓
Repository Overview
        ↓
Ask Codebase
        ↓
Investigate
        ↓
Plan Changes
        ↓
Review Proposed Changes
        ↓
Run Tests
        ↓
Validation Result
```

The backend API is already separated into distinct operations, making it possible to build a richer client without changing the core repository-analysis services.

---

# Project Goal

The long-term goal of AI Codebase Engineer is to provide an AI-assisted engineering workflow that helps developers move from:

```text
"I don't understand this repository."
```

to:

```text
"I understand the relevant code,
I know where the problem is,
I have a grounded implementation plan,
I can review the proposed change,
and I can validate the result."
```

The project focuses on making AI reasoning **codebase-aware and evidence-driven** rather than relying solely on generic AI responses.
