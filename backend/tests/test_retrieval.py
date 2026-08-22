from pathlib import Path

from app.services import score_chunks


def test_score_chunks_finds_matching_function():
    chunks = [
        {
            "name": "login_user",
            "file": "auth.py",
            "type": "function",
            "content": "def login_user(username, password):",
            "imports": [],
            "references": [],
            "start_line": 1,
            "end_line": 3,
        },
        {
            "name": "calculate_total",
            "file": "cart.py",
            "type": "function",
            "content": "return price * quantity",
            "imports": [],
            "references": [],
            "start_line": 1,
            "end_line": 3,
        },
    ]

    results = score_chunks(
        chunks,
        "login",
        5,
    )

    assert len(results) == 1
    assert results[0]["chunk"]["name"] == "login_user"


def test_score_chunks_respects_top_k():
    chunks = []

    for index in range(10):
        chunks.append({
            "name": f"login_function_{index}",
            "file": "auth.py",
            "type": "function",
            "content": "login authentication",
            "imports": [],
            "references": [],
            "start_line": 1,
            "end_line": 3,
        })

    results = score_chunks(
        chunks,
        "login",
        3,
    )

    assert len(results) == 3