"""Unit tests for pure/helper logic in app.services (no network, no real Gemini)."""
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import services
from app.services import (
    build_context_from_chunks,
    call_gemini_with_retry,
    chunks_path_for,
    detect_tests,
    load_chunks,
    remove_readonly,
    strip_code_fence,
)


# ------------------------------------------------------------
# strip_code_fence
# ------------------------------------------------------------

def test_strip_code_fence_removes_fence_and_language_tag():
    text = "```python\nprint(1)\n```"
    assert strip_code_fence(text) == "print(1)\n"


def test_strip_code_fence_leaves_plain_text_unchanged():
    text = "print(1)"
    assert strip_code_fence(text) == text


def test_strip_code_fence_handles_missing_closing_fence():
    text = "```\nx = 1"
    assert strip_code_fence(text) == "x = 1\n"


def test_strip_code_fence_ignores_surrounding_whitespace():
    text = "\n\n  ```js\nlet a = 1;\n```  \n"
    assert strip_code_fence(text) == "let a = 1;\n"


# ------------------------------------------------------------
# build_context_from_chunks
# ------------------------------------------------------------

def _result(name="login", file="auth.py"):
    return {
        "chunk": {
            "file": file,
            "language": "python",
            "type": "function",
            "name": name,
            "start_line": 1,
            "end_line": 5,
            "imports": ["os", "sys"],
            "references": ["helper"],
            "content": f"def {name}(): pass",
        }
    }


def test_build_context_empty_results_returns_fallback_message():
    assert build_context_from_chunks([]) == (
        "No relevant code was found for this question."
    )


def test_build_context_includes_chunk_details():
    context = build_context_from_chunks([_result()])
    assert "FILE: auth.py" in context
    assert "NAME: login" in context
    assert "LINES: 1-5" in context
    assert "os, sys" in context
    assert "def login(): pass" in context


def test_build_context_separates_multiple_chunks():
    context = build_context_from_chunks(
        [_result("a", "a.py"), _result("b", "b.py")]
    )
    assert "\n---\n" in context
    assert "FILE: a.py" in context and "FILE: b.py" in context


# ------------------------------------------------------------
# chunks_path_for / load_chunks / remove_readonly
# ------------------------------------------------------------

def test_chunks_path_for_uses_repo_name(tmp_path, monkeypatch):
    monkeypatch.setattr(services, "DATA_DIR", tmp_path)
    path = chunks_path_for(Path("/some/where/myrepo"))
    assert path == tmp_path / "myrepo_chunks.json"


def test_load_chunks_raises_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(services, "DATA_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_chunks(Path("/some/where/norepo"))


def test_load_chunks_returns_chunk_list(tmp_path, monkeypatch):
    monkeypatch.setattr(services, "DATA_DIR", tmp_path)
    (tmp_path / "demo_chunks.json").write_text(
        json.dumps({"chunks": [{"name": "f"}]}), encoding="utf-8"
    )
    assert load_chunks(Path("/x/demo")) == [{"name": "f"}]


def test_load_chunks_returns_empty_list_when_key_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(services, "DATA_DIR", tmp_path)
    (tmp_path / "demo_chunks.json").write_text("{}", encoding="utf-8")
    assert load_chunks(Path("/x/demo")) == []


def test_remove_readonly_deletes_read_only_file(tmp_path):
    target = tmp_path / "locked.txt"
    target.write_text("data")
    os.chmod(target, stat.S_IREAD)
    remove_readonly(os.remove, str(target), None)
    assert not target.exists()


# ------------------------------------------------------------
# detect_tests (pytest / npm / Maven / Gradle detection)
# ------------------------------------------------------------

def test_detect_tests_missing_path(tmp_path):
    result = detect_tests(tmp_path / "does_not_exist")
    assert result["success"] is False


def test_detect_tests_pytest_with_config(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]")
    (tmp_path / "test_app.py").write_text("def test_x(): pass")
    result = detect_tests(tmp_path)
    assert result["detected"] is True
    assert result["framework"] == "pytest"
    assert result["command"] == "python -m pytest"


def test_detect_tests_python_files_without_config(tmp_path):
    (tmp_path / "test_app.py").write_text("def test_x(): pass")
    result = detect_tests(tmp_path)
    assert result["detected"] is True
    assert result["framework"] == "python-unittest/pytest"


def test_detect_tests_npm_with_test_script(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "jest"}})
    )
    result = detect_tests(tmp_path)
    assert result["framework"] == "npm"
    assert result["command"] == "npm test"


def test_detect_tests_npm_without_test_script(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build"}})
    )
    result = detect_tests(tmp_path)
    assert result["detected"] is False


def test_detect_tests_ignores_invalid_package_json(tmp_path):
    (tmp_path / "package.json").write_text("{not valid json")
    result = detect_tests(tmp_path)
    assert result["detected"] is False


def test_detect_tests_maven(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    result = detect_tests(tmp_path)
    assert result["framework"] == "Maven"
    assert result["command"] == "mvn test"


@pytest.mark.parametrize("build_file", ["build.gradle", "build.gradle.kts"])
def test_detect_tests_gradle(tmp_path, build_file):
    (tmp_path / build_file).write_text("")
    result = detect_tests(tmp_path)
    assert result["framework"] == "Gradle"
    assert result["command"] == "gradle test"


def test_detect_tests_nothing_found(tmp_path):
    result = detect_tests(tmp_path)
    assert result["success"] is True
    assert result["detected"] is False
    assert result["framework"] is None


def test_detect_tests_pytest_config_without_test_files(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]")
    result = detect_tests(tmp_path)
    assert result["detected"] is False


# ------------------------------------------------------------
# call_gemini_with_retry (Gemini fully mocked)
# ------------------------------------------------------------

class FakeGemini:
    """Fake Gemini client: returns/raises items from a scripted list."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, model, contents):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(services.time, "sleep", recorded.append)
    return recorded


def test_gemini_returns_response_on_first_try(monkeypatch, sleeps):
    fake = FakeGemini(["ok"])
    monkeypatch.setattr(services, "gemini_client", fake)
    assert call_gemini_with_retry("hi") == "ok"
    assert fake.calls == 1
    assert sleeps == []


def test_gemini_retries_on_503_then_succeeds(monkeypatch, sleeps):
    fake = FakeGemini([Exception("503 UNAVAILABLE"), "ok"])
    monkeypatch.setattr(services, "gemini_client", fake)
    assert call_gemini_with_retry("hi") == "ok"
    assert fake.calls == 2
    assert sleeps == [1]


def test_gemini_does_not_retry_other_errors(monkeypatch, sleeps):
    fake = FakeGemini([ValueError("bad request")])
    monkeypatch.setattr(services, "gemini_client", fake)
    with pytest.raises(ValueError):
        call_gemini_with_retry("hi")
    assert fake.calls == 1


def test_gemini_raises_after_max_retries(monkeypatch, sleeps):
    fake = FakeGemini([Exception("503")] * 3)
    monkeypatch.setattr(services, "gemini_client", fake)
    with pytest.raises(Exception, match="503"):
        call_gemini_with_retry("hi", max_retries=3)
    assert fake.calls == 3
    assert sleeps == [1, 2]