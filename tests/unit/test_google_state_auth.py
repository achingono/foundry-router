"""Caller continuation scope is derived only from successful authentication."""

import base64
import json

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from foundry_router.api.google_state import credential_scope
from foundry_router.auth import verify_client_auth
from foundry_router.config import Settings


def test_caller_scope_header_bearer_rotation_and_no_raw_key(monkeypatch):
    scope_key = b"s" * 32
    settings = Settings(
        backends_json='{"g":{"provider":"google_ai_studio","endpoint":"https://fixture.example.test","credential":"fixture","deployment":"fixture","credit_metered":false}}',
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["fixture-client","fixture-rotated"]',
        admin_api_keys_json='["fixture-admin"]',
        google_state_keys_json=json.dumps(
            {
                "scope_key": base64.urlsafe_b64encode(scope_key).decode(),
                "keys": {"current": base64.urlsafe_b64encode(b"k" * 32).decode()},
                "active": "current",
                "generation": "fixture",
            }
        ),
    )
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: settings)
    app = FastAPI()
    captured = []

    @app.get("/fixture", dependencies=[Depends(verify_client_auth)])
    async def fixture(request: Request):
        captured.append(request.state.google_caller_scope)
        return {"authenticated": True}

    client = TestClient(app)
    for headers in (
        {"api-key": "fixture-client"},
        {"Authorization": "Bearer fixture-client"},
        {"api-key": "fixture-rotated"},
    ):
        response = client.get("/fixture", headers={**headers, "x-request-id": "caller-chosen"})
        assert response.json() == {"authenticated": True}
    assert captured[:2] == [credential_scope(scope_key, "fixture-client", domain="caller")] * 2
    assert captured[2] != captured[0]
    assert client.get("/fixture", headers={"api-key": "invalid"}).status_code == 401
    assert len(captured) == 3


@pytest.mark.parametrize("header", [{"api-key": "invalid"}, {}])
def test_invalid_authentication_never_reaches_scope_consumer(monkeypatch, header):
    app = FastAPI()
    settings = Settings(
        backends_json='{"a":{"endpoint":"https://fixture.example.test","credential":"fixture","deployment":"fixture"}}',
        models_json='{"m":{"backends":{"a":1}}}',
        client_api_keys_json='["fixture-client"]',
        admin_api_keys_json='["fixture-admin"]',
    )
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: settings)

    @app.get("/fixture", dependencies=[Depends(verify_client_auth)])
    async def fixture():
        pytest.fail("Unauthenticated scope consumer reached")

    assert TestClient(app).get("/fixture", headers=header).status_code == 401
