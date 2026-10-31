"""Input-validation tests for every POST route (no Gemini or network needed).

FastAPI/Pydantic rejects bad input with HTTP 422 before any handler runs.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# (path, valid payload) for every POST route that takes a JSON body.
VALID_PAYLOADS = [
    ("/ingest", {"repo_url": "https://github.com/example/repo"}),
    ("/analyze", {"cloned_to": "repos/example"}),
    ("/chunk", {"repo_path": "repos/example"}),
    ("/retrieve", {"repo_path": "repos/example", "query": "login"}),
    ("/context", {"repo_path": "repos/example", "query": "login"}),
    ("/prompt", {"repo_path": "repos/example", "question": "What does login do?"}),
    ("/ask", {"repo_path": "repos/example", "question": "What does login do?"}),
    ("/relationships", {"repo_path": "repos/example", "name": "login"}),
    ("/investigate", {"repo_path": "repos/example", "bug_description": "crash"}),
    ("/plan", {"repo_path": "repos/example", "feature_request": "add logging"}),
    (
        "/propose-change",
        {"repo_path": "repos/example", "file_path": "a.py", "instruction": "x"},
    ),
    ("/detect-tests", {"repo_path": "repos/example"}),
    ("/validate", {"repo_path": "repos/example"}),
]


@pytest.mark.parametrize("path,payload", VALID_PAYLOADS)
def test_empty_body_is_rejected(path, payload):
    response = client.post(path, json={})
    assert response.status_code == 422


@pytest.mark.parametrize("path,payload", VALID_PAYLOADS)
def test_empty_string_field_is_rejected(path, payload):
    for field in payload:
        bad = dict(payload)
        bad[field] = ""
        response = client.post(path, json=bad)
        assert response.status_code == 422, f"{path} accepted empty {field}"


@pytest.mark.parametrize(
    "path,payload",
    [item for item in VALID_PAYLOADS if "top_k" not in item[1]
     and item[0] in {"/retrieve", "/context", "/prompt", "/ask", "/investigate", "/plan"}],
)
@pytest.mark.parametrize("top_k", [0, 51, -1])
def test_top_k_out_of_range_is_rejected(path, payload, top_k):
    response = client.post(path, json={**payload, "top_k": top_k})
    assert response.status_code == 422