import json

from app.services import (
    get_relationships,
)


def test_relationships(tmp_path, monkeypatch):
    from app import services

    monkeypatch.setattr(
        services,
        "DATA_DIR",
        tmp_path,
    )

    repo_path = (
        tmp_path / "demo"
    )

    repo_path.mkdir()

    chunks_file = (
        tmp_path
        / "demo_chunks.json"
    )

    chunks_file.write_text(
        json.dumps({
            "chunks": [
                {
                    "name": "login_user",
                    "file": "auth.py",
                    "type": "function",
                    "start_line": 1,
                    "end_line": 5,
                    "imports": [
                        "database"
                    ],
                    "references": [
                        "validate_user"
                    ],
                },
                {
                    "name": "dashboard",
                    "file": "app.py",
                    "type": "function",
                    "start_line": 1,
                    "end_line": 5,
                    "imports": [],
                    "references": [
                        "login_user"
                    ],
                },
            ]
        }),
        encoding="utf-8",
    )

    result = get_relationships(
        repo_path,
        "login_user",
    )

    assert result["success"] is True

    assert (
        "validate_user"
        in result["depends_on"]
    )

    assert (
        result["used_by"][0]["name"]
        == "dashboard"
    )