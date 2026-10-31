from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_metrics_reports_request_counts_and_latency():
    client.get("/health")
    body = client.get("/metrics").json()

    assert body["total_requests"] >= 1
    assert "GET /health" in body["endpoints"]

    entry = body["endpoints"]["GET /health"]
    assert entry["count"] >= 1
    assert entry["avg_latency_ms"] >= 0
    assert entry["max_latency_ms"] >= entry["avg_latency_ms"]


def test_metrics_counts_error_responses():
    before = client.get("/metrics").json()["total_errors"]
    client.get("/route-that-does-not-exist")  # 404
    after = client.get("/metrics").json()["total_errors"]

    assert after == before + 1


def test_metrics_includes_uptime():
    body = client.get("/metrics").json()
    assert body["uptime_seconds"] >= 0