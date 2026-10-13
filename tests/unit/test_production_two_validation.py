"""Offline immutable four-slot production acceptance tests."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("scripts/quality").resolve()))
import production_two_validation as pv
import staging_validation as sv

from tests.unit.test_staging_validation import PLAN_DIR, roster_app


def setup(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(json.dumps(pv.MANIFEST))
    monkeypatch.setattr(sv, "STAGE_DIR", PLAN_DIR)
    return tmp_path


def app_for(environment):
    cases = [c for c in pv.CASES if c["id"].startswith(environment)]
    manifest = pv.case_manifest(cases[0])
    manifest["cases"] = cases
    app = roster_app(manifest)
    original = app._admin

    def admin():
        data = original()
        for pool in data["models"].values():
            pool["streaming_enabled"] = False
        if environment == "production":
            zen = data["credit_groups"].pop("zen-staging")
            data["credit_groups"]["fs-openclaw"] = zen
            data["credit_groups"]["fs-swarm"] = zen
        return data

    app._admin = admin
    return app


def run(tmp_path, app, environment="staging"):
    return pv.execute(
        environment,
        base_url="http://test",
        caller="client-key",
        admin="admin-key",
        directory=tmp_path,
        factory=lambda: app,
    )


def test_stage_then_production_and_no_replay(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    stage = app_for("staging")
    state = run(tmp_path, stage)
    assert len(stage.calls) == 2
    run(tmp_path, stage)
    assert len(stage.calls) == 2
    prod = app_for("production")
    state = run(tmp_path, prod, "production")
    assert len(prod.calls) == 2
    assert all(e["result"]["status"] == "passed" for e in state["entries"])


def test_missing_stage_blocks_production(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    app = app_for("production")
    with pytest.raises(ValueError):
        run(tmp_path, app, "production")
    assert app.calls == []


def test_setup_failure_reserved_no_replay(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    app = app_for("staging")
    original = app._admin

    def admin():
        data = original()
        for pool in data["models"].values():
            pool.pop("streaming_enabled")
        return data

    app._admin = admin
    with pytest.raises(ValueError):
        run(tmp_path, app)
    with pytest.raises(ValueError):
        run(tmp_path, app)
    assert app.calls == []


def test_manifest_mutation_refuses(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    data = json.loads((tmp_path / "manifest.json").read_text())
    data["image_digest"] = "sha256:other"
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        run(tmp_path, app_for("staging"))


def test_failure_halts_no_replay(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    app = app_for("staging")
    app.status_override = {"staging-0": (502, {})}
    with pytest.raises(ValueError):
        run(tmp_path, app)
    with pytest.raises(ValueError):
        run(tmp_path, app)
    assert len(app.calls) == 1
