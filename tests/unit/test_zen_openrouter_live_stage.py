"""Offline stage gates: sequencing, halt, replay refusal, persistence, locking."""

import fcntl
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import zen_openrouter_live_budget as budget
import zen_openrouter_live_runtime as runtime
import zen_openrouter_live_stage as stage


def manifest(**overrides):
    base = {
        "version": 1,
        "run": budget.RUN_ID,
        "zen_model": "gpt-5.4",
        "openrouter_model": "organization/model",
        "openrouter_embedding_model": "organization/embed",
        "input_per_million": 1000.0,
        "output_per_million": 1000.0,
        "cases": list(budget.CASE_IDS),
        "case_timeout_seconds": budget.CASE_TIMEOUT_SECONDS,
        "max_observed_bytes": budget.MAX_OBSERVED_BYTES,
        "max_output_tokens": budget.MAX_OUTPUT_TOKENS,
    }
    base.update(overrides)
    return base


def zen_payload(stream=False):
    if not stream:
        return json.dumps(
            {
                "id": "resp_1",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "ready"}],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            }
        ).encode()
    return (
        b'data: {"type":"response.created"}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"ready"}]}],"usage":{"input_tokens":10,"output_tokens":5,"total_tokens":15}}}\n\n'
    )


def chat_payload(stream=False):
    if not stream:
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ready"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ).encode()
    return (
        b'data: {"choices":[{"delta":{"content":"ready"},"finish_reason":"stop"}]}\n\n'
        b'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}\n\n'
        b"data: [DONE]\n\n"
    )


def embeddings_payload():
    return json.dumps(
        {
            "data": [
                {"index": 0, "embedding": [0.5, 1.0]},
                {"index": 1, "embedding": [1.5, 2.0]},
            ],
            "usage": {"prompt_tokens": 6, "total_tokens": 6},
        }
    ).encode()


class Switchboard(httpx.AsyncBaseTransport):
    """Route canned provider bytes by host/path; count every dispatch."""

    def __init__(self, failures=None):
        self.failures = failures or {}
        self.calls = 0

    async def handle_async_request(self, request):
        self.calls += 1
        host, path = request.url.host, request.url.path
        body = json.loads(request.content.decode())
        stream = body.get("stream") is True
        if path == "/zen/v1/responses":
            key = "zen-stream" if stream else "zen-nonstream"
        elif path == "/api/v1/chat/completions":
            key = "openrouter-stream" if stream else "openrouter-nonstream"
        elif path == "/api/v1/embeddings":
            key = "openrouter-embeddings"
        else:
            raise ValueError("unexpected upstream path")
        assert host in {"opencode.ai", "openrouter.ai"}
        status, payload = self.failures.get(key, (200, None))
        if payload is None:
            payload = {
                "zen-nonstream": zen_payload(),
                "zen-stream": zen_payload(stream=True),
                "openrouter-nonstream": chat_payload(),
                "openrouter-stream": chat_payload(stream=True),
                "openrouter-embeddings": embeddings_payload(),
            }[key]
        return httpx.Response(status, content=payload)

    async def aclose(self):
        pass


def run_stage(tmp_path, switchboard, manifest_data=None):
    manifest_data = manifest_data or manifest()
    return stage.execute_stage(
        manifest_data,
        stage_dir=tmp_path,
        ledger_path=tmp_path / "ledger.json",
        results_path=tmp_path / "results.json",
        zen_credential="synthetic-zen-credential",
        openrouter_credential="synthetic-or-credential",
        transport_factory=lambda: switchboard,
    )


def test_full_pass_and_idempotent_rerun(tmp_path):
    board = Switchboard()
    results = run_stage(tmp_path, board)
    assert [item["case_id"] for item in results["attempts"]] == list(budget.CASE_IDS)
    assert all(item["status"] == "passed" for item in results["attempts"])
    assert board.calls == 5
    rerun = run_stage(tmp_path, board)
    assert len(rerun["attempts"]) == 5
    assert board.calls == 5
    dumped = (tmp_path / "results.json").read_text() + (tmp_path / "ledger.json").read_text()
    assert "synthetic-zen-credential" not in dumped
    assert "synthetic-or-credential" not in dumped


def test_first_failure_halts_remaining_cases(tmp_path):
    board = Switchboard(failures={"zen-nonstream": (500, b"boom")})
    results = run_stage(tmp_path, board)
    assert len(results["attempts"]) == 1
    assert results["attempts"][0]["status"] == "failed"
    assert results["attempts"][0]["provider_http_status"] == 500
    assert board.calls == 1
    rerun = run_stage(tmp_path, board)
    assert len(rerun["attempts"]) == 1
    assert board.calls == 1


def test_stream_requires_passed_nonstream_within_stage(tmp_path):
    board = Switchboard(failures={"zen-nonstream": (500, b"boom")})
    results = run_stage(tmp_path, board)
    assert [item["case_id"] for item in results["attempts"]] == ["zen-nonstream"]
    assert board.calls == 1


def test_reserved_without_outcome_blocks_execution(tmp_path):
    board = Switchboard()
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    ledger.reserve("zen-nonstream")
    with pytest.raises(ValueError):
        run_stage(tmp_path, board)
    assert board.calls == 0


def test_manifest_mismatch_refuses(tmp_path):
    board = Switchboard()
    run_stage(tmp_path, board)
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, manifest(version=2))
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, manifest(zen_model="other-model"))
    assert board.calls == 5


def test_corrupt_results_refuse(tmp_path):
    board = Switchboard()
    run_stage(tmp_path, board)
    (tmp_path / "results.json").write_text('{"run": "other", "attempts": []}')
    with pytest.raises(ValueError):
        run_stage(tmp_path, board)
    assert board.calls == 5


@pytest.mark.parametrize(
    "mutation",
    [
        {"status": "passed", "dispatched": False},
        {"status": "passed", "error_category": "provider_or_protocol_failure"},
        {"status": "passed", "input_tokens": None},
        {"extra": True},
        {"http_status": -1},
    ],
)
def test_result_mutations_rejected(tmp_path, mutation):
    manifest_data = manifest()
    results = {
        "run": budget.RUN_ID,
        "manifest": stage.manifest_fingerprint(manifest_data),
        "attempts": [],
    }
    good = {
        "case_id": "zen-nonstream",
        "kind": "zen-nonstream",
        "stream": False,
        "status": "failed",
        "http_status": 500,
        "provider_http_status": 500,
        "dispatched": True,
        "input_tokens": None,
        "output_tokens": None,
        "usage_matches": False,
        "terminated_ok": False,
        "settlement_matches": False,
        "reservations_cleared": False,
        "synthetic_debit_usd": 0.0,
        "vector_count": 0,
        "dimensions": 0,
        "order_matches": False,
        "vector_values_match": False,
        "error_category": None,
        "elapsed_seconds": 0.1,
    }
    good.update(mutation)
    results["attempts"].append(good)
    with pytest.raises(ValueError):
        stage.load_results(tmp_path / "missing.json", manifest_data, data=results)


def test_over_cap_passed_result_rejected(tmp_path):
    manifest_data = manifest()
    results = {
        "run": budget.RUN_ID,
        "manifest": stage.manifest_fingerprint(manifest_data),
        "attempts": [
            {
                "case_id": "zen-nonstream",
                "kind": "zen-nonstream",
                "stream": False,
                "status": "passed",
                "http_status": 200,
                "provider_http_status": 200,
                "dispatched": True,
                "input_tokens": 10,
                "output_tokens": 129,
                "usage_matches": True,
                "terminated_ok": True,
                "settlement_matches": True,
                "reservations_cleared": True,
                "synthetic_debit_usd": 0.139,
                "vector_count": 0,
                "dimensions": 0,
                "order_matches": False,
                "vector_values_match": False,
                "error_category": None,
                "elapsed_seconds": 0.1,
            }
        ],
    }
    with pytest.raises(ValueError):
        stage.load_results(tmp_path / "missing.json", manifest_data, data=results)


def test_results_write_failure_blocks_without_replay(tmp_path):
    board = Switchboard()
    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
    results_file = ro_dir / "results.json"
    ro_dir.chmod(0o500)
    try:
        with pytest.raises((OSError, ValueError)):
            stage.execute_stage(
                manifest(),
                stage_dir=tmp_path,
                ledger_path=tmp_path / "ledger.json",
                results_path=results_file,
                zen_credential="synthetic-zen-credential",
                openrouter_credential="synthetic-or-credential",
                transport_factory=lambda: board,
            )
    finally:
        ro_dir.chmod(0o700)
    # The first case may have dispatched once; terminal completion cannot reset
    # the run, and the failed write must not permit a replay.
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    assert ledger._read()["dispatches"] == 1
    with pytest.raises(ValueError):
        run_stage(tmp_path, board)


def test_stage_lock_is_exclusive(tmp_path):
    with budget.locked(tmp_path / "stage"):
        with (tmp_path / "stage.lock").open("a") as handle:
            with pytest.raises(OSError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_cli_refuses_without_execute(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["zen_openrouter_live_stage.py"])
    assert stage.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_reports_ledger_dispatches_not_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stage, "STAGE_DIR", tmp_path)
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    ledger.reserve("zen-nonstream")
    monkeypatch.setattr(sys, "argv", ["zen_openrouter_live_stage.py"])
    assert stage.main() == 2
    report = json.loads(capsys.readouterr().out)["provider_requests"]
    assert report[budget.RUN_ID] == 1


def test_cli_reports_unknown_for_unreadable_ledger(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stage, "STAGE_DIR", tmp_path)
    (tmp_path / "ledger.json").write_text("corrupt")
    monkeypatch.setattr(sys, "argv", ["zen_openrouter_live_stage.py"])
    assert stage.main() == 2
    report = json.loads(capsys.readouterr().out)["provider_requests"]
    assert report[budget.RUN_ID] == "unknown"


def test_cli_refuses_missing_credentials(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest()))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "zen_openrouter_live_stage.py",
            "--execute",
            "--manifest",
            str(manifest_path),
        ],
    )
    monkeypatch.delenv("ZEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert stage.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "refused_or_interrupted"


def test_cli_rejects_path_overrides_and_binds_canonical_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["zen_openrouter_live_stage.py", "--execute", "--ledger", "other.json"]
    )
    with pytest.raises(SystemExit):
        stage.main()
    captured = {}

    def fake_execute(_manifest_data, **kwargs):
        captured.update(kwargs)
        return {"run": budget.RUN_ID, "attempts": []}

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest()))
    monkeypatch.setattr(
        sys,
        "argv",
        ["zen_openrouter_live_stage.py", "--execute", "--manifest", str(manifest_path)],
    )
    monkeypatch.setenv("ZEN_API_KEY", "synthetic-zen-credential")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-or-credential")
    monkeypatch.setattr(stage, "execute_stage", fake_execute)
    monkeypatch.setattr(stage, "STAGE_DIR", tmp_path)
    assert stage.main() == 0
    assert "ledger_path" not in captured and "results_path" not in captured


def test_deleted_ledger_after_pass_blocks_without_dispatch(tmp_path):
    board = Switchboard()
    run_stage(tmp_path, board)
    (tmp_path / "ledger.json").unlink()
    with pytest.raises(ValueError):
        run_stage(tmp_path, board)
    assert board.calls == 5


def test_reserved_case_without_ledger_outcome_blocks_restart(tmp_path):
    board = Switchboard()
    run_stage(tmp_path, board)
    ledger_path = tmp_path / "ledger.json"
    data = json.loads(ledger_path.read_text())
    data["cases"]["zen-nonstream"]["outcome"] = None
    data["cases"]["zen-nonstream"]["actual_tokens"] = None
    ledger_path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        run_stage(tmp_path, board)
    assert board.calls == 5


def test_ledger_outcome_without_matching_result_blocks_restart(tmp_path):
    board = Switchboard()
    run_stage(tmp_path, board)
    results_path = tmp_path / "results.json"
    results = json.loads(results_path.read_text())
    results["attempts"] = results["attempts"][1:]
    results_path.write_text(json.dumps(results))
    with pytest.raises(ValueError):
        run_stage(tmp_path, board)
    assert board.calls == 5


def test_setup_failure_blocks_without_ledger_outcome(tmp_path, monkeypatch):
    board = Switchboard()

    async def boom(**_kwargs):
        raise runtime.VerificationSetupError("not ready")

    monkeypatch.setattr(stage, "run_live_case", boom)
    with pytest.raises(ValueError, match="setup failed before dispatch"):
        run_stage(tmp_path, board)
    assert board.calls == 0
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    assert ledger.dispatch_count() == 0
    assert ledger.runnable("zen-nonstream") is True


def _passed_result(**overrides):
    result = {
        "case_id": "zen-nonstream",
        "kind": "zen-nonstream",
        "stream": False,
        "status": "passed",
        "http_status": 200,
        "provider_http_status": 200,
        "dispatched": True,
        "input_tokens": 10,
        "output_tokens": 5,
        "usage_matches": True,
        "terminated_ok": True,
        "settlement_matches": True,
        "reservations_cleared": True,
        "synthetic_debit_usd": 0.015,
        "vector_count": 0,
        "dimensions": 0,
        "order_matches": False,
        "vector_values_match": False,
        "error_category": None,
        "elapsed_seconds": 0.1,
    }
    result.update(overrides)
    return result


def _seeded(tmp_path, result):
    manifest_data = manifest()
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    ledger.reserve(result["case_id"])
    tokens = result["input_tokens"], result["output_tokens"]
    actual = tokens[0] + tokens[1] if all(type(v) is int for v in tokens) else None
    ledger.record_outcome(result["case_id"], actual, failed=result["status"] != "passed")
    (tmp_path / "results.json").write_text(
        json.dumps(
            {
                "run": budget.RUN_ID,
                "manifest": stage.manifest_fingerprint(manifest_data),
                "attempts": [result],
            }
        )
    )
    return manifest_data


def test_contradictory_success_blocks_resume(tmp_path):
    board = Switchboard()
    manifest_data = _seeded(tmp_path, _passed_result(http_status=500, provider_http_status=500))
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, manifest_data)
    assert board.calls == 0


def test_stream_mismatch_blocks_resume(tmp_path):
    board = Switchboard()
    manifest_data = _seeded(tmp_path, _passed_result(stream=True))
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, manifest_data)
    assert board.calls == 0


def test_embeddings_passed_without_vector_evidence_blocked(tmp_path):
    board = Switchboard()
    manifest_data = _seeded(
        tmp_path,
        _passed_result(
            case_id="openrouter-embeddings",
            kind="openrouter-embeddings",
            input_tokens=6,
            output_tokens=0,
            vector_count=0,
            dimensions=0,
            order_matches=False,
            vector_values_match=True,
        ),
    )
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, manifest_data)
    assert board.calls == 0


def test_non_embeddings_claiming_vectors_blocked(tmp_path):
    board = Switchboard()
    manifest_data = _seeded(
        tmp_path, _passed_result(vector_count=2, dimensions=3, order_matches=True)
    )
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, manifest_data)
    assert board.calls == 0


def prefix_manifest():
    return manifest(
        cases=list(budget.CASE_IDS[:4]),
        openrouter_embedding_model="",
    )


def test_prefix_run_completes_without_embeddings_dispatch(tmp_path):
    board = Switchboard()
    results = run_stage(tmp_path, board, prefix_manifest())
    assert [item["case_id"] for item in results["attempts"]] == list(budget.CASE_IDS[:4])
    assert all(item["status"] == "passed" for item in results["attempts"])
    assert board.calls == 4
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    assert ledger.runnable("openrouter-embeddings") is True
    rerun = run_stage(tmp_path, board, prefix_manifest())
    assert len(rerun["attempts"]) == 4
    assert board.calls == 4


def test_unlisted_result_rejected(tmp_path):
    board = Switchboard()
    run_stage(tmp_path, board, prefix_manifest())
    results_path = tmp_path / "results.json"
    results = json.loads(results_path.read_text())
    results["attempts"].append(
        {
            "case_id": "openrouter-embeddings",
            "kind": "openrouter-embeddings",
            "stream": False,
            "status": "failed",
            "http_status": None,
            "provider_http_status": None,
            "dispatched": False,
            "input_tokens": None,
            "output_tokens": None,
            "usage_matches": False,
            "terminated_ok": False,
            "settlement_matches": False,
            "reservations_cleared": False,
            "synthetic_debit_usd": 0.0,
            "vector_count": 0,
            "dimensions": 0,
            "order_matches": False,
            "vector_values_match": False,
            "error_category": None,
            "elapsed_seconds": 0.0,
        }
    )
    results_path.write_text(json.dumps(results))
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, prefix_manifest())
    assert board.calls == 4


def openrouter_manifest(**overrides):
    base = manifest(
        run=budget.RUN_ID_OPENROUTER,
        zen_model="",
        openrouter_embedding_model="",
        cases=["openrouter-nonstream", "openrouter-stream"],
    )
    base.update(overrides)
    return base


def test_openrouter_run_passes_on_separate_files(tmp_path):
    board = Switchboard()
    results = stage.execute_stage(
        openrouter_manifest(),
        stage_dir=tmp_path,
        zen_credential="synthetic-zen-credential",
        openrouter_credential="synthetic-or-credential",
        transport_factory=lambda: board,
    )
    assert [item["case_id"] for item in results["attempts"]] == [
        "openrouter-nonstream",
        "openrouter-stream",
    ]
    assert all(item["status"] == "passed" for item in results["attempts"])
    assert board.calls == 2
    assert (tmp_path / "ledger-openrouter.json").exists()
    assert (tmp_path / "results-openrouter.json").exists()
    assert not (tmp_path / "ledger.json").exists()


def test_openrouter_run_ignores_halted_default_run(tmp_path):
    board = Switchboard()
    halted = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    halted.reserve("zen-nonstream")
    halted.record_outcome("zen-nonstream", None, failed=True)
    results = stage.execute_stage(
        openrouter_manifest(),
        stage_dir=tmp_path,
        zen_credential="synthetic-zen-credential",
        openrouter_credential="synthetic-or-credential",
        transport_factory=lambda: board,
    )
    assert all(item["status"] == "passed" for item in results["attempts"])
    assert board.calls == 2


def test_unknown_run_identity_rejected(tmp_path):
    board = Switchboard()
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, openrouter_manifest(run="other-run"))
    assert board.calls == 0


def test_run_b_rejects_zen_model_on_record(tmp_path):
    board = Switchboard()
    with pytest.raises(ValueError):
        run_stage(tmp_path, board, openrouter_manifest(zen_model="gpt-5.4"))
    assert board.calls == 0


@pytest.mark.parametrize(
    "filename,ledger_name,results_name,cases",
    [
        (
            "manifest.zen-paid.json",
            "ledger-zen-paid.json",
            "results-zen-paid.json",
            ["zen-nonstream", "zen-stream"],
        ),
        (
            "manifest.or-openai.json",
            "ledger-or-openai.json",
            "results-or-openai.json",
            ["openrouter-nonstream", "openrouter-stream"],
        ),
        (
            "manifest.or-anthropic.json",
            "ledger-or-anthropic.json",
            "results-or-anthropic.json",
            ["openrouter-nonstream", "openrouter-stream"],
        ),
    ],
)
def test_paid_runs_pass_on_canonical_files(tmp_path, filename, ledger_name, results_name, cases):
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / f"docs/plans/zen-openrouter-live-verification/{filename}"
    )
    manifest_data = json.loads(manifest_path.read_text())
    board = Switchboard()
    results = stage.execute_stage(
        manifest_data,
        stage_dir=tmp_path,
        zen_credential="synthetic-zen-credential",
        openrouter_credential="synthetic-or-credential",
        transport_factory=lambda: board,
    )
    assert [item["case_id"] for item in results["attempts"]] == cases
    assert all(item["status"] == "passed" for item in results["attempts"])
    assert all(item["settlement_matches"] for item in results["attempts"])
    assert board.calls == 2
    assert (tmp_path / ledger_name).exists()
    assert (tmp_path / results_name).exists()
    rerun = stage.execute_stage(
        manifest_data,
        stage_dir=tmp_path,
        zen_credential="synthetic-zen-credential",
        openrouter_credential="synthetic-or-credential",
        transport_factory=lambda: board,
    )
    assert len(rerun["attempts"]) == 2
    assert board.calls == 2
