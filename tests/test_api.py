from __future__ import annotations

from fastapi.testclient import TestClient

from harmonica.api import create_app


def test_api_smoke() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json()["ok"] is True
    factors = client.get("/rating-factors")
    assert factors.status_code == 200
    assert {factor["key"] for factor in factors.json()} >= {"lyrics", "music", "overall"}

