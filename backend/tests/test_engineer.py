from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_engineer_requires_repo_url():
    response = client.post(
        "/engineer",
        json={
            "task_type": "plan",
            "question": "Add logging",
            "top_k": 5,
        },
    )

    assert response.status_code == 422


def test_engineer_requires_question():
    response = client.post(
        "/engineer",
        json={
            "repo_url": "https://github.com/example/repo",
            "task_type": "plan",
            "top_k": 5,
        },
    )

    assert response.status_code == 422


def test_engineer_rejects_invalid_task_type():
    response = client.post(
        "/engineer",
        json={
            "repo_url":
                "https://github.com/example/repo",
            "task_type":
                "something_else",
            "question":
                "Add logging",
            "top_k": 5,
        },
    )

    assert response.status_code == 422