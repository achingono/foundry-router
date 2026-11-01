from __future__ import annotations

import asyncio
import hashlib
import json
import ssl
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))

import ingress_watchdog.ledger as ledger_module
from ingress_watchdog.clock import FakeClock, SystemClock
from ingress_watchdog.errors import (
    AuthorizationError,
    ClockError,
    ClosedError,
    LedgerError,
    ProtocolError,
)
from ingress_watchdog.ledger import (
    AzureBlobCreateOnlyLedger,
    LedgerKind,
    MemoryCreateOnlyLedger,
    WormAttestation,
    WormAttestationBinding,
)
from ingress_watchdog.responses import ResponseInspector, ResponseLimits
from ingress_watchdog.schema import canonical_json, parse_canonical_json
from ingress_watchdog.signing import KeyRole, VerificationKey, sign_object, verify_object
from ingress_watchdog.state import GatewayState as BaseGatewayState
from ingress_watchdog.state import Packet, Phase, TrustedBudgetBinding
from ingress_watchdog.transport import (
    create_ingress_server_context,
    create_origin_client_context,
    open_fixed_origin,
    read_ingress_request,
    verify_tls_peer,
)

HASH = "a" * 64
PROGRAM_SCOPE = "f" * 64
BUDGET_NAMESPACE = "test-budget"
REGISTRY_NAMESPACE = "test-registry"
CYCLE_END = 1_850_000_000_000_000_000
RETAIN_UNTIL = 1_900_000_000_000_000_000


def memory_budget() -> MemoryCreateOnlyLedger:
    return MemoryCreateOnlyLedger(
        kind=LedgerKind.BUDGET,
        namespace=BUDGET_NAMESPACE,
        program_scope_sha256=PROGRAM_SCOPE,
        financial_retain_until_utc_ns=RETAIN_UNTIL,
    )


def memory_registry() -> MemoryCreateOnlyLedger:
    return MemoryCreateOnlyLedger(
        kind=LedgerKind.REGISTRY,
        namespace=REGISTRY_NAMESPACE,
        program_scope_sha256=PROGRAM_SCOPE,
        financial_retain_until_utc_ns=RETAIN_UNTIL,
    )


class GatewayState(BaseGatewayState):
    def __init__(self, **kwargs):
        keyring = kwargs["keyring"]
        now = kwargs["clock"].sample().utc_ns
        budget_namespace = kwargs.pop("trusted_budget_namespace", BUDGET_NAMESPACE)
        signed_binding = sign_object(
            "budget-namespace-binding",
            {
                "program_scope_sha256": PROGRAM_SCOPE,
                "budget_namespace_sha256": hashlib.sha256(budget_namespace.encode()).hexdigest(),
                "registry_namespace_sha256": hashlib.sha256(
                    REGISTRY_NAMESPACE.encode()
                ).hexdigest(),
                "funding_cycle_end_utc_ns": CYCLE_END,
                "audit_retain_until_utc_ns": RETAIN_UNTIL,
                "issued_utc_ns": now,
                "expires_utc_ns": now + 3600_000_000_000,
            },
            key_id="budget-authority",
            private_key=keyring.private_keys["budget-authority"],
        )
        signed_registry_binding = sign_object(
            "trusted-registry-binding",
            {
                "program_scope_sha256": PROGRAM_SCOPE,
                "registry_namespace_sha256": hashlib.sha256(
                    REGISTRY_NAMESPACE.encode()
                ).hexdigest(),
                "issued_utc_ns": now,
                "expires_utc_ns": now + 3600_000_000_000,
            },
            key_id="reviewer",
            private_key=keyring.private_keys["reviewer"],
        )
        registry = kwargs.pop("registry_ledger", None) or memory_registry()
        super().__init__(
            **kwargs,
            registry_ledger=registry,
            budget_binding=TrustedBudgetBinding(
                program_scope_sha256=PROGRAM_SCOPE,
                namespace=budget_namespace,
                registry_namespace=REGISTRY_NAMESPACE,
                funding_cycle_end_utc_ns=CYCLE_END,
                financial_retain_until_utc_ns=RETAIN_UNTIL,
                authority_key_id="budget-authority",
                signed_binding=signed_binding,
                registry_reviewer_key_id="reviewer",
                signed_registry_binding=signed_registry_binding,
            ),
        )


def signed_keys() -> tuple[dict[str, Ed25519PrivateKey], dict[str, VerificationKey]]:
    private = {
        role.value: Ed25519PrivateKey.generate()
        for role in (
            KeyRole.REVIEWER,
            KeyRole.BUDGET_AUTHORITY,
            KeyRole.SUPERVISOR,
            KeyRole.FINANCIAL_VERIFIER,
            KeyRole.GATEWAY,
            KeyRole.OPERATOR,
        )
    }

    class FixtureKeyring(dict):
        pass

    keyring = FixtureKeyring(
        {
            role: VerificationKey(role, KeyRole(role), key.public_key())
            for role, key in private.items()
        }
    )
    keyring.private_keys = private
    return private, keyring


def case_body(index: int) -> bytes:
    return json.dumps(
        {
            "model": "model-a" if index < 2 else "model-b",
            "stream": index % 2 == 1,
            "max_output_tokens": 128,
            "input": "test",
        },
        separators=(",", ":"),
    ).encode()


def packet_payload(
    clock: FakeClock,
    allocation_sha256: str,
) -> dict[str, object]:
    bodies = [case_body(index) for index in range(4)]
    cases = [
        {
            "case_id": f"case-{index}",
            "order": index,
            "deployment_id": "deployment-a" if index < 2 else "deployment-b",
            "body_sha256": hashlib.sha256(bodies[index]).hexdigest(),
            "model": "model-a" if index < 2 else "model-b",
            "stream": index % 2 == 1,
            "max_input_tokens": 64,
            "max_output_tokens": 128,
            "reserve_microusd": 1000,
        }
        for index in range(4)
    ]
    return {
        "packet_version": 1,
        "session_id": "session-01",
        "not_after_utc_ns": clock.utc_ns + 600_000_000_000,
        "origin_host": "isolated.example.internal",
        "origin_port": 443,
        "runner_identity_sha256": "b" * 64,
        "gateway_certificate_sha256": "c" * 64,
        "reviewer_key_id": "reviewer",
        "budget_authority_key_id": "budget-authority",
        "supervisor_key_id": "supervisor",
        "financial_verifier_key_id": "financial-verifier",
        "gateway_key_id": "gateway",
        "operator_key_id": "operator",
        "max_request_bytes": 4096,
        "lease_ttl_ns": 15_000_000_000,
        "allocation_id": "allocation-01",
        "allocation_sha256": allocation_sha256,
        "budget_namespace_sha256": hashlib.sha256(BUDGET_NAMESPACE.encode()).hexdigest(),
        "config_sha256": "d" * 64,
        "expected_deny_state_sha256": "b" * 64,
        "restart_target_sha256": "1" * 64,
        "baseline_state_sha256": "6" * 64,
        "baseline_accounts_sha256": "c" * 64,
        "baseline_process_id": "process-1",
        "denial_response_code_details": "direct_response",
        "diagnostic_calibration_sha256": "e" * 64,
        "aggregate_reserve_microusd": 4000,
        "routes": [
            {"method": "GET", "path": "/health/ready"},
            {"method": "GET", "path": "/admin/status"},
            {"method": "POST", "path": "/openai/v1/responses"},
        ],
        "cases": cases,
    }


def sign_packet(payload: dict[str, object], keys: dict[str, Ed25519PrivateKey]) -> bytes:
    return sign_object(
        "packet",
        payload,
        key_id="reviewer",
        private_key=keys["reviewer"],
    )


def signed_material(
    clock: FakeClock,
    keys: dict[str, Ed25519PrivateKey],
) -> tuple[bytes, bytes]:
    allocation = sign_object(
        "program-allocation",
        {
            "allocation_id": "allocation-01",
            "session_id": "session-01",
            "program_scope_sha256": "f" * 64,
            "budget_namespace_sha256": hashlib.sha256(BUDGET_NAMESPACE.encode()).hexdigest(),
            "prior_liabilities_sha256": "9" * 64,
            "funding_cycle_end_utc_ns": CYCLE_END,
            "audit_retain_until_utc_ns": RETAIN_UNTIL,
            "aggregate_limit_microusd": 1_000_000,
            "prior_liability_microusd": 0,
            "aggregate_attempt_limit": 16,
            "prior_attempts": 0,
            "case_ids": [f"case-{index}" for index in range(4)],
            "reserves_microusd": [1000] * 4,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="budget-authority",
        private_key=keys["budget-authority"],
    )
    payload = packet_payload(clock, hashlib.sha256(allocation).hexdigest())
    packet = sign_packet(payload, keys)
    return packet, allocation


def sign_heartbeat(
    clock: FakeClock,
    keys: dict[str, Ed25519PrivateKey],
    challenge: str,
) -> bytes:
    return sign_object(
        "heartbeat",
        {
            "session_id": "session-01",
            "challenge": challenge,
            "checked_at_utc_ns": clock.utc_ns,
            "process_id": 12,
            "process_start_id": "boot-identity-12",
        },
        key_id="supervisor",
        private_key=keys["supervisor"],
    )


def sign_worm_attestation(  # noqa: PLR0913 -- test attestation controls are independent
    clock: FakeClock,
    keys: dict[str, Ed25519PrivateKey],
    *,
    retention_days: int = 8,
    kind: LedgerKind = LedgerKind.SESSION,
    legal_hold: bool = False,
    scope: str | None = None,
    retain_until: int | None = None,
) -> bytes:
    return sign_object(
        "worm-attestation",
        {
            "account_url": "https://acct.blob.core.windows.net",
            "container_name": "watchdog-ledger",
            "managed_identity_client_id": "00000000-0000-0000-0000-000000000001",
            "kind": kind.value,
            "program_scope_sha256": scope,
            "financial_retain_until_utc_ns": retain_until,
            "legal_hold": legal_hold,
            "legal_hold_clear_denied": legal_hold,
            "policy_locked": True,
            "retention_days": retention_days,
            "overwrite_denied": True,
            "delete_denied": True,
            "primary_endpoint_url": "https://acct.blob.core.windows.net",
            "automatic_failover": False,
            "retry_total": 0,
            "retry_connect": 0,
            "retry_read": 0,
            "retry_status": 0,
            "retry_to_secondary": False,
            "policy_evidence_sha256": "4" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 60_000_000_000,
        },
        key_id="operator",
        private_key=keys["operator"],
    )


class FakeManagedIdentityCredential:
    def __init__(self, client_id: str) -> None:
        self._credential = SimpleNamespace(_settings={"client_id": client_id})


def fake_blob_container(
    *,
    client_id: str,
    blob: object,
    retries: int = 0,
    environment_proxy: bool = False,
) -> SimpleNamespace:
    blob_client = blob
    credential = FakeManagedIdentityCredential(client_id)
    retry_policy = SimpleNamespace(
        total_retries=retries,
        connect_retries=retries,
        read_retries=retries,
        status_retries=retries,
        retry_to_secondary=False,
    )
    transport = SimpleNamespace(_use_env_settings=environment_proxy)
    return SimpleNamespace(
        url="https://acct.blob.core.windows.net/watchdog-ledger",
        credential=credential,
        _config=SimpleNamespace(retry_policy=retry_policy, transport=transport),
        get_blob_client=lambda *, blob: blob_client if blob else None,
    )


async def complete_case(
    state: GatewayState,
    clock: FakeClock,
    private: dict[str, Ed25519PrivateKey],
    case_index: int,
) -> None:
    case_id = f"case-{case_index}"
    permit = await state.prepare_dispatch(case_id, case_body(case_index))
    clock.advance(100_000_000)
    receipt = sign_object(
        "pre-dispatch-receipt",
        {
            "session_id": "session-01",
            "case_id": case_id,
            "dispatch_sha256": permit.record_sha256,
            "config_sha256": "d" * 64,
            "snapshot_sha256": "7" * 64,
            "prior_state_sha256": "6" * 64,
            "snapshot_observed_utc_ns": clock.utc_ns,
            "snapshot_uncertainty_ns": clock.uncertainty_ns,
            "input_upper_bound_tokens": 64,
            "cost_ceiling_microusd": 1000,
            "cost_proof_sha256": "4" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 2_000_000_000,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    await state.authorize_and_initiate(permit, receipt, lambda: True)
    witness = sign_object(
        "response-witness",
        {
            "session_id": "session-01",
            "case_id": case_id,
            "dispatch_sha256": permit.record_sha256,
            "response_sha256": "8" * 64,
            "issued_utc_ns": clock.utc_ns,
            "status_code": 200,
            "completed": True,
            "clean_eof": True,
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        },
        key_id="gateway",
        private_key=private["gateway"],
    )
    settlement = sign_object(
        "settlement",
        {
            "session_id": "session-01",
            "case_id": case_id,
            "dispatch_sha256": permit.record_sha256,
            "response_witness_sha256": hashlib.sha256(witness).hexdigest(),
            "post_snapshot_sha256": "6" * 64,
            "post_state_sha256": "6" * 64,
            "accounts_sha256": "c" * 64,
            "process_id": "process-1",
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    await state.advance(witness, settlement)


def test_canonical_json_rejects_noncanonical_and_duplicate_fields() -> None:
    assert parse_canonical_json(b'{"a":1,"b":true}') == {"a": 1, "b": True}
    for raw in (
        b'{"b":true,"a":1}',
        b'{"a":1,"a":2}',
        b'{"a":1.0}',
        b'{"a":NaN}',
        '{"name":"caf\u00e9"}'.encode(),
    ):
        with pytest.raises(ProtocolError):
            parse_canonical_json(raw)
    with pytest.raises(ProtocolError):
        canonical_json({"amount": 1.5})


def test_signed_objects_are_domain_separated_and_role_checked() -> None:
    private, keyring = signed_keys()
    signed = sign_object(
        "packet",
        {"session_id": "session-01"},
        key_id="reviewer",
        private_key=private["reviewer"],
    )
    assert verify_object(
        signed,
        expected_kind="packet",
        expected_role=KeyRole.REVIEWER,
        keyring=keyring,
    ) == {"session_id": "session-01"}
    with pytest.raises(AuthorizationError):
        verify_object(
            signed,
            expected_kind="packet",
            expected_role=KeyRole.SUPERVISOR,
            keyring=keyring,
        )
    envelope = parse_canonical_json(signed)
    assert isinstance(envelope, dict)
    envelope["kind"] = "heartbeat"
    with pytest.raises(AuthorizationError):
        verify_object(
            canonical_json(envelope),
            expected_kind="packet",
            expected_role=KeyRole.REVIEWER,
            keyring=keyring,
        )


def test_packet_binds_four_cases_two_deployments_and_stream_modes() -> None:
    clock = FakeClock()
    payload = packet_payload(clock, HASH)
    packet = Packet.parse(payload, raw_sha256=HASH)
    assert len(packet.cases) == 4
    invalid = dict(payload)
    invalid["routes"] = [{"method": "POST", "path": "/other"}]
    with pytest.raises(ProtocolError):
        Packet.parse(invalid, raw_sha256=HASH)
    invalid = dict(payload)
    invalid["cases"] = list(payload["cases"])
    invalid["cases"][1] = dict(invalid["cases"][1], stream=False)
    with pytest.raises(ProtocolError):
        Packet.parse(invalid, raw_sha256=HASH)


def test_worm_attestation_is_signed_fresh_and_bound_to_storage_identity() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    binding = WormAttestationBinding(
        operator_key_id="operator",
        kind=LedgerKind.SESSION,
        account_url="https://acct.blob.core.windows.net",
        container_name="watchdog-ledger",
        managed_identity_client_id="00000000-0000-0000-0000-000000000001",
    )
    attestation = WormAttestation.verify(
        sign_worm_attestation(clock, private),
        keyring=keyring,
        binding=binding,
        now_utc_ns=clock.utc_ns,
        uncertainty_ns=clock.uncertainty_ns,
    )
    assert attestation.policy_evidence_sha256 == "4" * 64

    with pytest.raises(AuthorizationError):
        WormAttestation.verify(
            sign_worm_attestation(clock, private, retention_days=7),
            keyring=keyring,
            binding=binding,
            now_utc_ns=clock.utc_ns,
            uncertainty_ns=clock.uncertainty_ns,
        )
    with pytest.raises(AuthorizationError):
        WormAttestation.verify(
            sign_worm_attestation(clock, private),
            keyring=keyring,
            binding=WormAttestationBinding(
                operator_key_id="operator",
                kind=LedgerKind.SESSION,
                account_url="https://different.blob.core.windows.net",
                container_name="watchdog-ledger",
                managed_identity_client_id="00000000-0000-0000-0000-000000000001",
            ),
            now_utc_ns=clock.utc_ns,
            uncertainty_ns=clock.uncertainty_ns,
        )


@pytest.mark.asyncio
async def test_blob_ledger_is_single_attempt_conditional_and_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    client_id = "00000000-0000-0000-0000-000000000001"
    binding = WormAttestationBinding(
        operator_key_id="operator",
        kind=LedgerKind.SESSION,
        account_url="https://acct.blob.core.windows.net",
        container_name="watchdog-ledger",
        managed_identity_client_id=client_id,
    )
    monkeypatch.setattr(
        ledger_module.importlib,
        "import_module",
        lambda _name: SimpleNamespace(ManagedIdentityCredential=FakeManagedIdentityCredential),
    )

    class Upload:
        def __init__(self, *, fail: bool = False) -> None:
            self.calls: list[tuple[bytes, dict[str, object]]] = []
            self.fail = fail

        def upload_blob(
            self,
            data: bytes,
            **kwargs: object,
        ) -> dict[str, object]:
            self.calls.append((data, kwargs))
            if self.fail:
                raise TimeoutError("ambiguous response")
            return {"etag": '"etag-1"'}

    blob = Upload()
    container = fake_blob_container(client_id=client_id, blob=blob)
    adapter = AzureBlobCreateOnlyLedger(
        container,
        signed_attestation=sign_worm_attestation(clock, private),
        keyring=keyring,
        binding=binding,
        clock=clock,
    )
    first_digest = hashlib.sha256(b"record").hexdigest()
    record_name = f"arm/{hashlib.sha256(b'session-01').hexdigest()}/{first_digest}"
    assert await adapter.create(record_name, b"record") == hashlib.sha256(b"record").hexdigest()
    assert blob.calls == [
        (
            b"record",
            {
                "overwrite": False,
                "if_none_match": "*",
                "max_concurrency": 1,
            },
        )
    ]
    with pytest.raises(LedgerError, match="invalid ledger record"):
        await adapter.create("../bad", b"record")
    clock.advance(61_000_000_000)
    with pytest.raises(LedgerError, match="expired"):
        await adapter.create(record_name, b"record")
    assert len(blob.calls) == 1

    broken_blob = Upload(fail=True)
    broken = AzureBlobCreateOnlyLedger(
        fake_blob_container(client_id=client_id, blob=broken_blob),
        signed_attestation=sign_worm_attestation(clock, private),
        keyring=keyring,
        binding=binding,
        clock=clock,
    )
    with pytest.raises(LedgerError, match="ambiguous"):
        await broken.create(record_name.replace("arm/", "close/"), b"record")
    assert len(broken_blob.calls) == 1


def test_blob_ledger_refuses_retry_proxy_and_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    client_id = "00000000-0000-0000-0000-000000000001"
    binding = WormAttestationBinding(
        operator_key_id="operator",
        kind=LedgerKind.SESSION,
        account_url="https://acct.blob.core.windows.net",
        container_name="watchdog-ledger",
        managed_identity_client_id=client_id,
    )
    monkeypatch.setattr(
        ledger_module.importlib,
        "import_module",
        lambda _name: SimpleNamespace(ManagedIdentityCredential=FakeManagedIdentityCredential),
    )
    attestation = sign_worm_attestation(clock, private)
    with pytest.raises(LedgerError, match="retries"):
        AzureBlobCreateOnlyLedger(
            fake_blob_container(client_id=client_id, blob=object(), retries=1),
            signed_attestation=attestation,
            keyring=keyring,
            binding=binding,
            clock=clock,
        )
    with pytest.raises(LedgerError, match="environment"):
        AzureBlobCreateOnlyLedger(
            fake_blob_container(
                client_id=client_id,
                blob=object(),
                environment_proxy=True,
            ),
            signed_attestation=attestation,
            keyring=keyring,
            binding=binding,
            clock=clock,
        )
    with pytest.raises(LedgerError, match="managed identity"):
        AzureBlobCreateOnlyLedger(
            fake_blob_container(
                client_id="00000000-0000-0000-0000-000000000002",
                blob=object(),
            ),
            signed_attestation=attestation,
            keyring=keyring,
            binding=binding,
            clock=clock,
        )


def test_system_clock_rejects_missing_or_untrusted_time(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    monkeypatch.delattr(time, "CLOCK_BOOTTIME", raising=False)
    with pytest.raises(ClockError, match="unavailable"):
        SystemClock(lambda: (True, 0))

    monkeypatch.setattr(time, "CLOCK_BOOTTIME", 7, raising=False)
    monkeypatch.setattr(time, "clock_gettime_ns", lambda _clock_id: 20)
    monkeypatch.setattr(time, "time_ns", lambda: 100)
    monkeypatch.setattr(time, "monotonic_ns", lambda: 30)
    sample = SystemClock(lambda: (False, 1)).sample()
    assert sample.trusted is False
    with pytest.raises(ClockError, match="uncertainty"):
        SystemClock(lambda: (True, 2_000_000_001)).sample()


@pytest.mark.asyncio
async def test_ingress_parser_accepts_only_bounded_fixed_requests() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(
        b"POST /openai/v1/responses HTTP/1.1\r\n"
        b"Host: isolated.example.internal\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 2\r\n"
        b"api-key: unit-test-key\r\n"
        b"Connection: close\r\n\r\n{}"
    )
    reader.feed_eof()
    request = await read_ingress_request(
        reader,
        origin_host="isolated.example.internal",
        max_request_bytes=16,
        peer_role="runner",
        forwarding_open=True,
    )
    assert request.method == b"POST"
    assert request.target == b"/openai/v1/responses"
    assert "unit-test-key" not in repr(request)
    assert request.body == b"{}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw",
    [
        (
            b"POST /openai/v1/responses?x=1 HTTP/1.1\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.1\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\n"
            b"Connection: close\r\n\r\n{}"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.1\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n"
            b"Connection: close\r\n\r\n"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.1\r\nHost: wrong.example.internal\r\n"
            b"Content-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.1\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.1\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: application/json\r\nContent-Length: 02\r\nConnection: close\r\n\r\n{}"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.1\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: application/json\r\nContent-Length: 2\r\nConnection: keep-alive\r\n\r\n{}"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.0\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
        ),
        (
            b"POST /openai/v1/responses HTTP/1.1\r\nHost: isolated.example.internal\r\n"
            b"Content-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
            b"GET /health/ready HTTP/1.1\r\nHost: isolated.example.internal\r\n\r\n"
        ),
        b"GET /other HTTP/1.1\r\nHost: isolated.example.internal\r\nConnection: close\r\n\r\n",
    ],
)
async def test_ingress_parser_rejects_ambiguous_or_unapproved_requests(raw: bytes) -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(raw)
    reader.feed_eof()
    with pytest.raises((ProtocolError, AuthorizationError)):
        await read_ingress_request(
            reader,
            origin_host="isolated.example.internal",
            max_request_bytes=16,
            peer_role="runner",
            forwarding_open=True,
        )


@pytest.mark.asyncio
async def test_ingress_reader_bounds_body_and_times_out_closed() -> None:
    oversized = asyncio.StreamReader()
    oversized.feed_data(
        b"POST /openai/v1/responses HTTP/1.1\r\nHost: isolated.example.internal\r\n"
        b"Content-Type: application/json\r\nContent-Length: 2\r\napi-key: key\r\nConnection: close\r\n\r\n{}"
    )
    oversized.feed_eof()
    with pytest.raises(ProtocolError, match="packet limit"):
        await read_ingress_request(
            oversized,
            origin_host="isolated.example.internal",
            max_request_bytes=1,
            peer_role="runner",
            forwarding_open=True,
        )

    idle = asyncio.StreamReader()
    with pytest.raises(ProtocolError, match="timed out"):
        await read_ingress_request(
            idle,
            origin_host="isolated.example.internal",
            max_request_bytes=16,
            peer_role="runner",
            forwarding_open=True,
            timeout_seconds=0.01,
        )

    with pytest.raises(ProtocolError, match="timeout"):
        await read_ingress_request(
            asyncio.StreamReader(),
            origin_host="isolated.example.internal",
            max_request_bytes=16,
            peer_role="runner",
            forwarding_open=True,
            timeout_seconds=0,
        )

    closed = asyncio.StreamReader()
    closed.feed_eof()
    with pytest.raises(ProtocolError, match="closed"):
        await read_ingress_request(
            closed,
            origin_host="isolated.example.internal",
            max_request_bytes=16,
            peer_role="runner",
            forwarding_open=True,
        )


@pytest.mark.asyncio
async def test_tls_contexts_require_client_identity_and_pin_leaf_certificate(
    tmp_path: Path,
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_file = tmp_path / "certificate.pem"
    key_file = tmp_path / "private-key.pem"
    certificate_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    certificate_sha256 = hashlib.sha256(
        certificate.public_bytes(serialization.Encoding.DER)
    ).hexdigest()
    server_context = create_ingress_server_context(
        certificate_file=str(certificate_file),
        private_key_file=str(key_file),
        client_ca_file=str(certificate_file),
    )
    client_context = create_origin_client_context(
        origin_ca_file=str(certificate_file),
        client_certificate_file=str(certificate_file),
        client_private_key_file=str(key_file),
    )
    peer_verified = asyncio.Event()

    async def accept_client(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        verify_tls_peer(writer, expected_certificate_sha256=certificate_sha256)
        peer_verified.set()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(
        accept_client,
        host="127.0.0.1",
        port=0,
        ssl=server_context,
    )
    try:
        port = server.sockets[0].getsockname()[1]
        _reader, writer = await asyncio.open_connection(
            "127.0.0.1",
            port,
            ssl=client_context,
            server_hostname="localhost",
        )
        verify_tls_peer(writer, expected_certificate_sha256=certificate_sha256)
        with pytest.raises(AuthorizationError):
            verify_tls_peer(writer, expected_certificate_sha256="0" * 64)
        with pytest.raises(ProtocolError, match="fingerprint"):
            verify_tls_peer(writer, expected_certificate_sha256="bad")
        with pytest.raises(AuthorizationError, match="TLS"):
            verify_tls_peer(
                SimpleNamespace(get_extra_info=lambda _name: None),
                expected_certificate_sha256=certificate_sha256,
            )
        insecure_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        insecure_context.check_hostname = False
        insecure_context.verify_mode = ssl.CERT_NONE
        with pytest.raises(ProtocolError, match="configuration"):
            await open_fixed_origin(
                "localhost",
                ssl_context=insecure_context,
                expected_certificate_sha256=certificate_sha256,
            )
        await asyncio.wait_for(peer_verified.wait(), timeout=1)
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()


def test_nonstream_response_inspection_binds_usage_and_exact_body_hash() -> None:
    body = b'{"id":"response-1","status":"completed","usage":{"input_tokens":10,"output_tokens":20,"total_tokens":30}}'
    inspector = ResponseInspector(
        case_id="case-0",
        status_code=200,
        streaming=False,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    assert inspector.feed(body[:20]) == body[:20]
    assert inspector.feed(body[20:]) == body[20:]
    evidence = inspector.finish(issued_utc_ns=1_800_000_000_000_000_000)
    assert evidence.response_sha256 == hashlib.sha256(body).hexdigest()
    assert (evidence.input_tokens, evidence.output_tokens) == (10, 20)
    assert evidence.completed is True
    assert evidence.clean_eof is True


def test_streaming_response_inspection_handles_fragmented_sse_without_mutation() -> None:
    completion = (
        b"event: response.completed\r\n"
        b'data: {"type":"response.completed","response":{"status":"completed",'
        b'"usage":{"input_tokens":12,"output_tokens":24,"total_tokens":36}}}\r\n\r\n'
    )
    inspector = ResponseInspector(
        case_id="case-1",
        status_code=200,
        streaming=True,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    chunks = [b"event: response.in_progress\ndata: {}\n\n", completion[:17], completion[17:]]
    for chunk in chunks:
        assert inspector.feed(chunk) is chunk
    evidence = inspector.finish(issued_utc_ns=1_800_000_000_000_000_000)
    assert evidence.response_sha256 == hashlib.sha256(b"".join(chunks)).hexdigest()
    assert (evidence.input_tokens, evidence.output_tokens) == (12, 24)


def test_response_inspector_rejects_bad_status_usage_and_terminal_sequences() -> None:
    with pytest.raises(ProtocolError, match="HTTP 200"):
        ResponseInspector(
            case_id="case-0",
            status_code=204,
            streaming=False,
            limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
        )
    bad_json = ResponseInspector(
        case_id="case-0",
        status_code=200,
        streaming=False,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    bad_json.feed(b'{"status":"completed","usage":{"input_tokens":1,"input_tokens":2}}')
    with pytest.raises(ProtocolError, match="duplicate"):
        bad_json.finish(issued_utc_ns=1)

    failed = ResponseInspector(
        case_id="case-0",
        status_code=200,
        streaming=True,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    with pytest.raises(ProtocolError, match="failed or incomplete"):
        failed.feed(b"event: response.failed\ndata: {}\n\n")

    duplicate = ResponseInspector(
        case_id="case-0",
        status_code=200,
        streaming=True,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    event = (
        b'event: response.completed\ndata: {"type":"response.completed",'
        b'"response":{"status":"completed","usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2}}}\n\n'
    )
    duplicate.feed(event)
    with pytest.raises(ProtocolError, match="after the terminal"):
        duplicate.feed(event)

    incomplete = ResponseInspector(
        case_id="case-0",
        status_code=200,
        streaming=True,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    incomplete.feed(b"event: response.completed\ndata: {")
    with pytest.raises(ProtocolError, match="incomplete event"):
        incomplete.finish(issued_utc_ns=1)


@pytest.mark.parametrize("event_header", [b"", b"event: response.completed\n"])
def test_response_inspector_accepts_data_only_terminal_and_done(event_header: bytes) -> None:
    inspector = ResponseInspector(
        case_id="case-1",
        status_code=200,
        streaming=True,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    data = (
        event_header + b'data: {"type":"response.completed","response":{"status":"completed",'
        b'"usage":{"input_tokens":2,"output_tokens":3,"total_tokens":5}}}\n\n'
        b"data: [DONE]\n\n"
    )
    for part in (data[:11], data[11:57], data[57:]):
        assert inspector.feed(part) == part
    assert inspector.finish(issued_utc_ns=1).total_tokens == 5


@pytest.mark.parametrize(
    "failure", [b'data: {"type":"response.failed"}\n\n', b'data: {"error":{"message":"no"}}\n\n']
)
def test_response_inspector_rejects_data_only_failure(failure: bytes) -> None:
    inspector = ResponseInspector(
        case_id="case-1",
        status_code=200,
        streaming=True,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    with pytest.raises(ProtocolError, match="failed or incomplete"):
        inspector.feed(failure)


@pytest.mark.parametrize("event", [b"response.failed", b"response.incomplete", b"error"])
def test_empty_failure_event_terminally_invalidates_inspector(event: bytes) -> None:
    inspector = ResponseInspector(
        case_id="case-1",
        status_code=200,
        streaming=True,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    with pytest.raises(ProtocolError, match="failed or incomplete"):
        inspector.feed(b"event: " + event + b"\n\n")
    with pytest.raises(ProtocolError, match="after EOF"):
        inspector.feed(b"data: {}\n\n")
    with pytest.raises(ProtocolError, match="already recorded"):
        inspector.finish(issued_utc_ns=1)


@pytest.mark.parametrize("total", [None, -1, True, 99])
def test_response_inspector_requires_consistent_total(total: object) -> None:
    import json

    usage = {"input_tokens": 2, "output_tokens": 3}
    if total is not None:
        usage["total_tokens"] = total
    inspector = ResponseInspector(
        case_id="case-0",
        status_code=200,
        streaming=False,
        limits=ResponseLimits(max_input_tokens=64, max_output_tokens=128),
    )
    inspector.feed(json.dumps({"status": "completed", "usage": usage}).encode())
    with pytest.raises(ProtocolError):
        inspector.finish(issued_utc_ns=1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "path", "credential", "allowed"),
    [
        ("runner", b"/openai/v1/responses", b"api-key: test-key", True),
        ("verifier", b"/openai/v1/responses", b"api-key: test-key", False),
        ("runner", b"/admin/status", b"x-admin-key: test-admin", False),
        ("verifier", b"/admin/status", b"x-admin-key: test-admin", True),
    ],
)
async def test_ingress_enforces_authenticated_role_and_redacts(
    role: str,
    path: bytes,
    credential: bytes,
    allowed: bool,
) -> None:
    method = b"POST" if path.endswith(b"responses") else b"GET"
    body = b"{}" if method == b"POST" else b""
    content = b"Content-Type: application/json\r\nContent-Length: 2\r\n" if body else b""
    reader = asyncio.StreamReader()
    reader.feed_data(
        method
        + b" "
        + path
        + b" HTTP/1.1\r\nHost: isolated.example.internal\r\n"
        + content
        + credential
        + b"\r\nConnection: close\r\n\r\n"
        + body
    )
    reader.feed_eof()
    call = read_ingress_request(
        reader,
        origin_host="isolated.example.internal",
        max_request_bytes=64,
        peer_role=role,
        forwarding_open=True,
    )
    if allowed:
        request = await call
        assert b"test-" not in repr(request).encode()
    else:
        with pytest.raises(AuthorizationError):
            await call


@pytest.mark.asyncio
async def test_arm_requires_reviewer_signature_and_heartbeat() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    state = GatewayState(
        clock=clock,
        ledger=MemoryCreateOnlyLedger(),
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    signed, allocation = signed_material(clock, private)
    packet = await state.arm(signed, allocation)
    assert packet.session_id == "session-01"
    assert state.phase is Phase.ARMED
    challenge = await state.issue_challenge()
    heartbeat = sign_heartbeat(clock, private, challenge)
    await state.renew(heartbeat)
    assert state.phase is Phase.ACTIVE


@pytest.mark.asyncio
async def test_dispatch_requires_fresh_verifier_receipt_and_is_one_shot() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    budget_ledger = memory_budget()
    state = GatewayState(
        clock=clock,
        ledger=ledger,
        budget_ledger=budget_ledger,
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    await state.arm(packet, allocation)
    challenge = await state.issue_challenge()
    await state.renew(sign_heartbeat(clock, private, challenge))

    body = case_body(0)
    permit = await state.prepare_dispatch("case-0", body)
    clock.advance(100_000_000)
    budget_slot = "/".join(
        (
            "program-slot",
            hashlib.sha256(b"allocation-01").hexdigest(),
            hashlib.sha256(b"case-0").hexdigest(),
        )
    )
    assert budget_slot in await budget_ledger.record_names()
    receipt = sign_object(
        "pre-dispatch-receipt",
        {
            "session_id": "session-01",
            "case_id": "case-0",
            "dispatch_sha256": permit.record_sha256,
            "config_sha256": "d" * 64,
            "snapshot_sha256": "7" * 64,
            "prior_state_sha256": "6" * 64,
            "snapshot_observed_utc_ns": clock.utc_ns,
            "snapshot_uncertainty_ns": clock.uncertainty_ns,
            "input_upper_bound_tokens": 64,
            "cost_ceiling_microusd": 1000,
            "cost_proof_sha256": "4" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 2_000_000_000,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    initiated: list[bool] = []

    def initiate_write() -> bool:
        initiated.append(True)
        return True

    await state.authorize_and_initiate(permit, receipt, initiate_write)
    assert initiated == [True]
    with pytest.raises(AuthorizationError):
        await state.authorize_and_initiate(permit, receipt, lambda: True)
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_case_advancement_requires_gateway_witness_and_verifier_settlement() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    state = GatewayState(
        clock=clock,
        ledger=MemoryCreateOnlyLedger(),
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    await state.arm(packet, allocation)
    challenge = await state.issue_challenge()
    await state.renew(sign_heartbeat(clock, private, challenge))
    permit = await state.prepare_dispatch("case-0", case_body(0))
    clock.advance(100_000_000)
    receipt = sign_object(
        "pre-dispatch-receipt",
        {
            "session_id": "session-01",
            "case_id": "case-0",
            "dispatch_sha256": permit.record_sha256,
            "config_sha256": "d" * 64,
            "snapshot_sha256": "7" * 64,
            "prior_state_sha256": "6" * 64,
            "snapshot_observed_utc_ns": clock.utc_ns,
            "snapshot_uncertainty_ns": clock.uncertainty_ns,
            "input_upper_bound_tokens": 64,
            "cost_ceiling_microusd": 1000,
            "cost_proof_sha256": "4" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 2_000_000_000,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    await state.authorize_and_initiate(permit, receipt, lambda: True)
    witness = sign_object(
        "response-witness",
        {
            "session_id": "session-01",
            "case_id": "case-0",
            "dispatch_sha256": permit.record_sha256,
            "response_sha256": "8" * 64,
            "issued_utc_ns": clock.utc_ns,
            "status_code": 200,
            "completed": True,
            "clean_eof": True,
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        },
        key_id="gateway",
        private_key=private["gateway"],
    )
    settlement = sign_object(
        "settlement",
        {
            "session_id": "session-01",
            "case_id": "case-0",
            "dispatch_sha256": permit.record_sha256,
            "response_witness_sha256": hashlib.sha256(witness).hexdigest(),
            "post_snapshot_sha256": "6" * 64,
            "post_state_sha256": "6" * 64,
            "accounts_sha256": "c" * 64,
            "process_id": "process-1",
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    await state.advance(witness, settlement)
    assert state.phase is Phase.ACTIVE
    assert state.next_case_id == "case-1"


@pytest.mark.asyncio
async def test_four_case_close_deny_probe_restart_lifecycle_is_one_way() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(
        clock=clock,
        ledger=ledger,
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    await state.arm(packet, allocation)
    challenge = await state.issue_challenge()
    await state.renew(sign_heartbeat(clock, private, challenge))

    for case_index in range(4):
        await complete_case(state, clock, private, case_index)
    assert state.next_case_id is None

    health_challenge = await state.issue_pre_deny_health_challenge()
    clock.advance(100_000_000)
    health = sign_object(
        "pre-deny-health",
        {
            "session_id": "session-01",
            "origin_host": "isolated.example.internal",
            "status_code": 200,
            "tls_valid": True,
            "request_id": "health-1",
            "challenge": health_challenge,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="gateway",
        private_key=private["gateway"],
    )
    await state.record_pre_deny_health(health)
    close_hash = await state.close_for_deny()
    deny_authorization = sign_object(
        "deny-authorization",
        {
            "session_id": "session-01",
            "close_sha256": close_hash,
            "deny_config_sha256": "b" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="operator",
        private_key=private["operator"],
    )
    await state.authorize_deny(deny_authorization)

    async def record_probe(phase: str, marker: str, authorization: bytes) -> bytes:
        clock.advance(100_000_000)
        probe_started = clock.utc_ns
        clock.advance(100_000_000)
        ingress_started = clock.utc_ns
        clock.advance(100_000_000)
        response_observed = clock.utc_ns
        clock.advance(100_000_000)
        gateway_attestation = sign_object(
            "origin-probe-attestation",
            {
                "session_id": "session-01",
                "phase": phase,
                "origin_host": "isolated.example.internal",
                "status_code": 403,
                "tls_valid": True,
                "request_id": f"probe-{phase}",
                "probe_marker_sha256": marker,
                "probe_started_utc_ns": probe_started,
                "probe_uncertainty_ns": clock.uncertainty_ns,
                "response_observed_utc_ns": response_observed,
                "response_uncertainty_ns": clock.uncertainty_ns,
                "response_sha256": "5" * 64,
                "issued_utc_ns": clock.utc_ns,
            },
            key_id="gateway",
            private_key=private["gateway"],
        )
        if phase == "pre-restart":
            # Diagnostic logs can arrive after the five-second operation window.
            clock.advance(6_000_000_000)
        verifier_proof = sign_object(
            "origin-probe-proof",
            {
                "session_id": "session-01",
                "phase": phase,
                "gateway_attestation_sha256": hashlib.sha256(gateway_attestation).hexdigest(),
                "request_id": f"probe-{phase}",
                "probe_marker_sha256": marker,
                "authorization_sha256": hashlib.sha256(authorization).hexdigest(),
                "diagnostic_calibration_sha256": "e" * 64,
                "response_code_details": "direct_response",
                "upstream_request_attempt_count": 0,
                "app_log_absent": True,
                "app_logs_complete": True,
                "diagnostics_sha256": "a" * 64,
                "arm_state_sha256": "b" * 64,
                "diagnostics_observed_utc_ns": clock.utc_ns,
                "arm_observed_utc_ns": clock.utc_ns,
                "ingress_started_utc_ns": ingress_started,
                "ingress_uncertainty_ns": clock.uncertainty_ns,
                "issued_utc_ns": clock.utc_ns,
            },
            key_id="financial-verifier",
            private_key=private["financial-verifier"],
        )
        await state.record_probe_result(gateway_attestation, verifier_proof)
        return verifier_proof

    pre_authorization = sign_object(
        "probe-authorization",
        {
            "session_id": "session-01",
            "phase": "pre-restart",
            "request_id": "probe-pre-restart",
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
            "proof_expires_utc_ns": clock.utc_ns + 60_000_000_000,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    pre_marker = await state.consume_probe("pre-restart", pre_authorization)
    pre_proof = await record_probe("pre-restart", pre_marker, pre_authorization)
    restart_authorization = sign_object(
        "restart-authorization",
        {
            "session_id": "session-01",
            "target_config_sha256": "d" * 64,
            "restart_target_sha256": "1" * 64,
            "pre_probe_proof_sha256": hashlib.sha256(pre_proof).hexdigest(),
            "process_before": "process-1",
            "accounts_sha256": "c" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
        },
        key_id="operator",
        private_key=private["operator"],
    )
    restart_marker = await state.authorize_restart(restart_authorization)
    restart_nonce = await state.initiate_restart(
        restart_marker, lambda _nonce: clock.advance(100_000_000) or True
    )
    start_proof = sign_object(
        "restart-start-proof",
        {
            "session_id": "session-01",
            "restart_marker_sha256": restart_marker,
            "restart_target_sha256": "1" * 64,
            "operation_started_utc_ns": clock.utc_ns,
            "operation_uncertainty_ns": clock.uncertainty_ns,
            "initiation_nonce": restart_nonce,
            "evidence_sha256": "2" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    restart_attestation = sign_object(
        "restart-attestation",
        {
            "session_id": "session-01",
            "process_before": "process-1",
            "process_after": "process-2",
            "restart_marker_sha256": restart_marker,
            "pre_probe_proof_sha256": hashlib.sha256(pre_proof).hexdigest(),
            "target_config_sha256": "d" * 64,
            "restart_target_sha256": "1" * 64,
            "start_proof_sha256": hashlib.sha256(start_proof).hexdigest(),
            "ready": True,
            "sole_worker": True,
            "accounts_sha256": "c" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="operator",
        private_key=private["operator"],
    )
    await state.record_restart(restart_attestation, start_proof)
    post_authorization = sign_object(
        "probe-authorization",
        {
            "session_id": "session-01",
            "phase": "post-restart",
            "request_id": "probe-post-restart",
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
            "proof_expires_utc_ns": clock.utc_ns + 60_000_000_000,
        },
        key_id="financial-verifier",
        private_key=private["financial-verifier"],
    )
    post_marker = await state.consume_probe("post-restart", post_authorization)
    await record_probe("post-restart", post_marker, post_authorization)

    assert state.phase is Phase.DENY_PROBES
    names = await ledger.record_names()
    assert sum(name.startswith("probe/") for name in names) == 2
    assert sum(name.startswith("probe-proof/") for name in names) == 2


@pytest.mark.asyncio
async def test_duplicate_arm_after_restart_is_rejected_by_create_only_ledger() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    signed, allocation = signed_material(clock, private)
    first = GatewayState(
        clock=clock,
        ledger=ledger,
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    await first.arm(signed, allocation)
    second = GatewayState(
        clock=clock,
        ledger=ledger,
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    with pytest.raises(LedgerError):
        await second.arm(signed, allocation)
    assert second.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_cancellation_during_arm_terminally_closes_gateway() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    started = asyncio.Event()

    async def block_create(_name: str, _payload: bytes) -> None:
        started.set()
        await asyncio.Event().wait()

    ledger.before_create = block_create
    state = GatewayState(
        clock=clock,
        ledger=ledger,
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    task = asyncio.create_task(state.arm(packet, allocation))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_stale_or_replayed_heartbeat_closes_session() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    state = GatewayState(
        clock=clock,
        ledger=MemoryCreateOnlyLedger(),
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    await state.arm(packet, allocation)
    challenge = await state.issue_challenge()
    heartbeat = sign_heartbeat(clock, private, challenge)
    await state.renew(heartbeat)
    with pytest.raises(AuthorizationError):
        await state.renew(heartbeat)
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_host_suspension_invalidates_session_before_new_challenge() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    state = GatewayState(
        clock=clock,
        ledger=MemoryCreateOnlyLedger(),
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    await state.arm(packet, allocation)
    clock.suspend(3_000_000_000)
    with pytest.raises(ClockError, match="suspension"):
        await state.issue_challenge()
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_clock_failure_during_close_terminally_closes_gateway() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    state = GatewayState(
        clock=clock,
        ledger=MemoryCreateOnlyLedger(),
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    await state.arm(packet, allocation)
    challenge = await state.issue_challenge()
    await state.renew(sign_heartbeat(clock, private, challenge))
    clock.trusted = False

    with pytest.raises(ClockError):
        await state.close_for_deny()
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_late_dispatch_ledger_completion_cannot_reopen_after_close() -> None:
    clock = FakeClock()
    private, keyring = signed_keys()
    entered = asyncio.Event()
    release = asyncio.Event()
    ledger = MemoryCreateOnlyLedger()

    async def pause_before_write(_: str, __: bytes) -> None:
        entered.set()
        await release.wait()

    state = GatewayState(
        clock=clock,
        ledger=ledger,
        budget_ledger=memory_budget(),
        keyring=keyring,
    )
    packet, allocation = signed_material(clock, private)
    await state.arm(packet, allocation)
    challenge = await state.issue_challenge()
    await state.renew(sign_heartbeat(clock, private, challenge))

    ledger.before_create = pause_before_write
    body = case_body(0)
    dispatch = asyncio.create_task(state.prepare_dispatch("case-0", body))
    await entered.wait()
    await state.fail_closed()
    release.set()
    with pytest.raises(ClosedError):
        await dispatch
    assert state.phase is Phase.TERMINAL
    assert any("dispatch" in name for name in await ledger.record_names())


@pytest.mark.asyncio
async def test_same_program_scope_cannot_arm_two_different_allocations() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    packet_a, allocation_a = signed_material(clock, keys)
    allocation_data = dict(parse_canonical_json(allocation_a)["payload"])
    allocation_data.update(allocation_id="allocation-02", session_id="session-02")
    allocation_b = sign_object(
        "program-allocation",
        allocation_data,
        key_id="budget-authority",
        private_key=keys["budget-authority"],
    )
    packet_data = dict(parse_canonical_json(packet_a)["payload"])
    packet_data.update(
        allocation_id="allocation-02",
        session_id="session-02",
        allocation_sha256=hashlib.sha256(allocation_b).hexdigest(),
    )
    shared_budget, shared_session = memory_budget(), MemoryCreateOnlyLedger()
    first = GatewayState(
        clock=clock, ledger=shared_session, budget_ledger=shared_budget, keyring=keyring
    )
    second = GatewayState(
        clock=clock, ledger=shared_session, budget_ledger=shared_budget, keyring=keyring
    )
    await first.arm(packet_a, allocation_a)
    with pytest.raises(LedgerError):
        await second.arm(sign_packet(packet_data, keys), allocation_b)
    assert second.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_common_registry_fences_conflicting_signed_budget_namespaces() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    packet_a, allocation_a = signed_material(clock, keys)
    second_namespace = "test-budget-2"
    allocation_data = dict(parse_canonical_json(allocation_a)["payload"])
    allocation_data.update(
        allocation_id="allocation-02",
        session_id="session-02",
        budget_namespace_sha256=hashlib.sha256(second_namespace.encode()).hexdigest(),
    )
    allocation_b = sign_object(
        "program-allocation",
        allocation_data,
        key_id="budget-authority",
        private_key=keys["budget-authority"],
    )
    packet_data = dict(parse_canonical_json(packet_a)["payload"])
    packet_data.update(
        allocation_id="allocation-02",
        session_id="session-02",
        allocation_sha256=hashlib.sha256(allocation_b).hexdigest(),
        budget_namespace_sha256=hashlib.sha256(second_namespace.encode()).hexdigest(),
    )
    second_budget = MemoryCreateOnlyLedger(
        kind=LedgerKind.BUDGET,
        namespace=second_namespace,
        program_scope_sha256=PROGRAM_SCOPE,
        financial_retain_until_utc_ns=RETAIN_UNTIL,
    )
    shared_registry = memory_registry()
    first = GatewayState(
        clock=clock,
        ledger=MemoryCreateOnlyLedger(),
        budget_ledger=memory_budget(),
        registry_ledger=shared_registry,
        keyring=keyring,
    )
    second = GatewayState(
        clock=clock,
        ledger=MemoryCreateOnlyLedger(),
        budget_ledger=second_budget,
        registry_ledger=shared_registry,
        trusted_budget_namespace=second_namespace,
        keyring=keyring,
    )
    await first.arm(packet_a, allocation_a)
    with pytest.raises(LedgerError):
        await second.arm(sign_packet(packet_data, keys), allocation_b)


@pytest.mark.asyncio
async def test_signed_allocation_cannot_shorten_required_financial_retention() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    packet, allocation = signed_material(clock, keys)
    allocation_data = dict(parse_canonical_json(allocation)["payload"])
    allocation_data["audit_retain_until_utc_ns"] = CYCLE_END
    altered = sign_object(
        "program-allocation",
        allocation_data,
        key_id="budget-authority",
        private_key=keys["budget-authority"],
    )
    packet_data = dict(parse_canonical_json(packet)["payload"])
    packet_data["allocation_sha256"] = hashlib.sha256(altered).hexdigest()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    with pytest.raises(AuthorizationError, match="aggregate limits"):
        await state.arm(sign_packet(packet_data, keys), altered)


def test_budget_namespace_must_match_independent_binding() -> None:
    clock = FakeClock()
    _, keyring = signed_keys()
    other = MemoryCreateOnlyLedger(
        kind=LedgerKind.BUDGET,
        namespace="wrong-container",
        program_scope_sha256=PROGRAM_SCOPE,
        financial_retain_until_utc_ns=RETAIN_UNTIL,
    )
    with pytest.raises(AuthorizationError, match="ledger bindings"):
        GatewayState(
            clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=other, keyring=keyring
        )


def test_registry_namespace_is_independently_pinned_from_budget_authority() -> None:
    from dataclasses import replace

    clock = FakeClock()
    keys, keyring = signed_keys()
    good = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    original = good._budget_binding
    data = dict(parse_canonical_json(original.signed_binding)["payload"])
    data["registry_namespace_sha256"] = hashlib.sha256(b"rogue-registry").hexdigest()
    signed = sign_object(
        "budget-namespace-binding",
        data,
        key_id="budget-authority",
        private_key=keys["budget-authority"],
    )
    altered = replace(original, registry_namespace="rogue-registry", signed_binding=signed)
    rogue = MemoryCreateOnlyLedger(
        kind=LedgerKind.REGISTRY,
        namespace="rogue-registry",
        program_scope_sha256=PROGRAM_SCOPE,
        financial_retain_until_utc_ns=RETAIN_UNTIL,
    )
    with pytest.raises(AuthorizationError, match="namespace binding"):
        BaseGatewayState(
            clock=clock,
            ledger=MemoryCreateOnlyLedger(),
            budget_ledger=memory_budget(),
            registry_ledger=rogue,
            keyring=keyring,
            budget_binding=altered,
        )


def test_budget_binding_rejects_zero_audit_window() -> None:
    from dataclasses import replace

    clock = FakeClock()
    _, keyring = signed_keys()
    good = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    altered = replace(good._budget_binding, funding_cycle_end_utc_ns=RETAIN_UNTIL)
    with pytest.raises(AuthorizationError, match="ledger bindings"):
        BaseGatewayState(
            clock=clock,
            ledger=MemoryCreateOnlyLedger(),
            budget_ledger=memory_budget(),
            registry_ledger=memory_registry(),
            keyring=keyring,
            budget_binding=altered,
        )


def test_budget_worm_requires_financial_retention_and_legal_hold() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    retain_until = clock.utc_ns + 30 * 86_400_000_000_000
    binding = WormAttestationBinding(
        operator_key_id="operator",
        account_url="https://acct.blob.core.windows.net",
        container_name="watchdog-ledger",
        managed_identity_client_id="00000000-0000-0000-0000-000000000001",
        kind=LedgerKind.BUDGET,
        program_scope_sha256=PROGRAM_SCOPE,
        financial_retain_until_utc_ns=retain_until,
    )

    def validate(days: int, hold: bool) -> WormAttestation:
        return WormAttestation.verify(
            sign_worm_attestation(
                clock,
                keys,
                retention_days=days,
                kind=LedgerKind.BUDGET,
                legal_hold=hold,
                scope=PROGRAM_SCOPE,
                retain_until=retain_until,
            ),
            keyring=keyring,
            binding=binding,
            now_utc_ns=clock.utc_ns,
            uncertainty_ns=clock.uncertainty_ns,
        )

    with pytest.raises(AuthorizationError, match="retention or legal hold"):
        validate(8, True)
    with pytest.raises(AuthorizationError, match="retention or legal hold"):
        validate(31, False)
    assert validate(31, True).container_name == "watchdog-ledger"


@pytest.mark.asyncio
async def test_blob_write_finishing_after_worm_attestation_expiry_is_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    client_id = "00000000-0000-0000-0000-000000000001"
    binding = WormAttestationBinding(
        operator_key_id="operator",
        kind=LedgerKind.SESSION,
        account_url="https://acct.blob.core.windows.net",
        container_name="watchdog-ledger",
        managed_identity_client_id=client_id,
    )
    monkeypatch.setattr(
        ledger_module.importlib,
        "import_module",
        lambda _name: SimpleNamespace(ManagedIdentityCredential=FakeManagedIdentityCredential),
    )

    class Upload:
        def upload_blob(self, _data: bytes, **_kwargs: object) -> dict[str, str]:
            clock.advance(61_000_000_000)
            return {"etag": '"committed"'}

    adapter = AzureBlobCreateOnlyLedger(
        fake_blob_container(client_id=client_id, blob=Upload()),
        signed_attestation=sign_worm_attestation(clock, keys),
        keyring=keyring,
        binding=binding,
        clock=clock,
    )
    with pytest.raises(LedgerError, match="expired during"):
        await adapter.create(f"arm/{'a' * 64}/{'b' * 64}", b"record")


@pytest.mark.asyncio
async def test_request_semantics_are_checked_before_any_slot_record() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    signed, allocation = signed_material(clock, keys)
    payload = dict(parse_canonical_json(signed)["payload"])
    cases = list(payload["cases"])
    cases[0] = dict(cases[0], model="wrong-model")
    payload["cases"] = cases
    budget = memory_budget()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=budget, keyring=keyring
    )
    await state.arm(sign_packet(payload, keys), allocation)
    await state.renew(sign_heartbeat(clock, keys, await state.issue_challenge()))
    with pytest.raises(AuthorizationError, match="semantics"):
        await state.prepare_dispatch("case-0", case_body(0))
    assert not any(name.startswith("program-slot/") for name in await budget.record_names())


@pytest.mark.asyncio
async def test_signed_body_with_context_amplification_is_refused_before_slot() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    signed, allocation = signed_material(clock, keys)
    body_data = json.loads(case_body(0))
    body_data["previous_response_id"] = "prior"
    body = json.dumps(body_data, separators=(",", ":")).encode()
    payload = dict(parse_canonical_json(signed)["payload"])
    cases = list(payload["cases"])
    cases[0] = dict(cases[0], body_sha256=hashlib.sha256(body).hexdigest())
    payload["cases"] = cases
    budget = memory_budget()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=budget, keyring=keyring
    )
    await state.arm(sign_packet(payload, keys), allocation)
    await state.renew(sign_heartbeat(clock, keys, await state.issue_challenge()))
    with pytest.raises(AuthorizationError, match="stateless text"):
        await state.prepare_dispatch("case-0", body)
    assert not any(name.startswith("program-slot/") for name in await budget.record_names())


async def ready_for_close(
    state: GatewayState, clock: FakeClock, keys: dict[str, Ed25519PrivateKey]
) -> None:
    packet, allocation = signed_material(clock, keys)
    await state.arm(packet, allocation)
    await state.renew(sign_heartbeat(clock, keys, await state.issue_challenge()))
    for index in range(4):
        await complete_case(state, clock, keys, index)
    health_challenge = await state.issue_pre_deny_health_challenge()
    clock.advance(100_000_000)
    health = sign_object(
        "pre-deny-health",
        {
            "session_id": "session-01",
            "origin_host": "isolated.example.internal",
            "status_code": 200,
            "tls_valid": True,
            "challenge": health_challenge,
            "request_id": "health-1",
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="gateway",
        private_key=keys["gateway"],
    )
    await state.record_pre_deny_health(health)


def deny_authorization(
    clock: FakeClock, keys: dict[str, Ed25519PrivateKey], close_hash: str
) -> bytes:
    return sign_object(
        "deny-authorization",
        {
            "session_id": "session-01",
            "close_sha256": close_hash,
            "deny_config_sha256": "b" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="operator",
        private_key=keys["operator"],
    )


@pytest.mark.asyncio
async def test_close_marker_finishing_after_lease_expiry_fails_closed() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(clock=clock, ledger=ledger, budget_ledger=memory_budget(), keyring=keyring)
    await ready_for_close(state, clock, keys)
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(name: str, _payload: bytes) -> None:
        if name.startswith("close/"):
            entered.set()
            await release.wait()

    ledger.before_create = hold
    task = asyncio.create_task(state.close_for_deny())
    await entered.wait()
    clock.advance(16_000_000_000)
    release.set()
    with pytest.raises(ClosedError, match="lease expiry"):
        await task
    assert state.phase is Phase.TERMINAL
    assert any(name.startswith("close/") for name in await ledger.record_names())


@pytest.mark.asyncio
async def test_stale_pre_deny_health_refuses_close_while_lease_live() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(clock=clock, ledger=ledger, budget_ledger=memory_budget(), keyring=keyring)
    await ready_for_close(state, clock, keys)
    clock.advance(6_000_000_000)
    with pytest.raises(ClosedError):
        await state.close_for_deny()
    assert state.phase is Phase.TERMINAL
    assert not any(name.startswith("close/") for name in await ledger.record_names())


@pytest.mark.asyncio
async def test_deny_marker_finishing_after_packet_expiry_refuses_mutation() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(clock=clock, ledger=ledger, budget_ledger=memory_budget(), keyring=keyring)
    await ready_for_close(state, clock, keys)
    close_hash = await state.close_for_deny()
    signed = deny_authorization(clock, keys, close_hash)
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(name: str, _payload: bytes) -> None:
        if name.startswith("deny/"):
            entered.set()
            await release.wait()

    ledger.before_create = hold
    task = asyncio.create_task(state.authorize_deny(signed))
    await entered.wait()
    clock.advance(601_000_000_000)
    release.set()
    with pytest.raises(ClosedError, match="authorization expiry"):
        await task
    assert state.phase is Phase.TERMINAL
    assert any(name.startswith("deny/") for name in await ledger.record_names())


@pytest.mark.asyncio
async def test_receipt_with_wrong_prior_state_cannot_start_write() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    packet, allocation = signed_material(clock, keys)
    await state.arm(packet, allocation)
    await state.renew(sign_heartbeat(clock, keys, await state.issue_challenge()))
    permit = await state.prepare_dispatch("case-0", case_body(0))
    clock.advance(100_000_000)
    receipt = sign_object(
        "pre-dispatch-receipt",
        {
            "session_id": "session-01",
            "case_id": "case-0",
            "dispatch_sha256": permit.record_sha256,
            "config_sha256": "d" * 64,
            "snapshot_sha256": "7" * 64,
            "prior_state_sha256": "0" * 64,
            "snapshot_observed_utc_ns": clock.utc_ns,
            "snapshot_uncertainty_ns": clock.uncertainty_ns,
            "input_upper_bound_tokens": 64,
            "cost_ceiling_microusd": 1000,
            "cost_proof_sha256": "4" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 2_000_000_000,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    writes: list[bool] = []
    with pytest.raises(AuthorizationError):
        await state.authorize_and_initiate(permit, receipt, lambda: writes.append(True) or True)
    assert not writes
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["input", "cost", "snapshot", "ordering"])
async def test_invalid_cost_or_stale_snapshot_never_starts_write(mutation: str) -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    packet, allocation = signed_material(clock, keys)
    await state.arm(packet, allocation)
    await state.renew(sign_heartbeat(clock, keys, await state.issue_challenge()))
    permit = await state.prepare_dispatch("case-0", case_body(0))
    clock.advance(100_000_000)
    data = {
        "session_id": "session-01",
        "case_id": "case-0",
        "dispatch_sha256": permit.record_sha256,
        "config_sha256": "d" * 64,
        "snapshot_sha256": "7" * 64,
        "prior_state_sha256": "6" * 64,
        "snapshot_observed_utc_ns": clock.utc_ns,
        "snapshot_uncertainty_ns": clock.uncertainty_ns,
        "input_upper_bound_tokens": 64,
        "cost_ceiling_microusd": 1000,
        "cost_proof_sha256": "4" * 64,
        "issued_utc_ns": clock.utc_ns,
        "expires_utc_ns": clock.utc_ns + 2_000_000_000,
    }
    if mutation == "input":
        data["input_upper_bound_tokens"] = 65
    elif mutation == "cost":
        data["cost_ceiling_microusd"] = 1001
    elif mutation == "snapshot":
        data["snapshot_observed_utc_ns"] -= 6_000_000_000
    else:
        data["snapshot_observed_utc_ns"] = permit.prepared_utc_ns - 1_000_000_000
    receipt = sign_object(
        "pre-dispatch-receipt",
        data,
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    writes: list[bool] = []
    with pytest.raises(AuthorizationError):
        await state.authorize_and_initiate(permit, receipt, lambda: writes.append(True) or True)
    assert not writes


@pytest.mark.asyncio
async def test_snapshot_freshness_includes_both_clock_uncertainties() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    packet, allocation = signed_material(clock, keys)
    await state.arm(packet, allocation)
    await state.renew(sign_heartbeat(clock, keys, await state.issue_challenge()))
    permit = await state.prepare_dispatch("case-0", case_body(0))
    clock.advance(8_500_000_000)
    receipt = sign_object(
        "pre-dispatch-receipt",
        {
            "session_id": "session-01",
            "case_id": "case-0",
            "dispatch_sha256": permit.record_sha256,
            "config_sha256": "d" * 64,
            "snapshot_sha256": "7" * 64,
            "prior_state_sha256": "6" * 64,
            "snapshot_observed_utc_ns": permit.prepared_utc_ns + 2_000_000_000,
            "snapshot_uncertainty_ns": 1_900_000_000,
            "input_upper_bound_tokens": 64,
            "cost_ceiling_microusd": 1000,
            "cost_proof_sha256": "4" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 2_000_000_000,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    writes: list[bool] = []
    with pytest.raises(AuthorizationError):
        await state.authorize_and_initiate(permit, receipt, lambda: writes.append(True) or True)
    assert not writes


@pytest.mark.asyncio
async def test_restart_cannot_be_authorized_after_unverified_probe() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(clock=clock, ledger=ledger, budget_ledger=memory_budget(), keyring=keyring)
    await ready_for_close(state, clock, keys)
    close_hash = await state.close_for_deny()
    await state.authorize_deny(deny_authorization(clock, keys, close_hash))
    probe = sign_object(
        "probe-authorization",
        {
            "session_id": "session-01",
            "phase": "pre-restart",
            "request_id": "probe-pre",
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
            "proof_expires_utc_ns": clock.utc_ns + 60_000_000_000,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    await state.consume_probe("pre-restart", probe)
    authorization = sign_object(
        "restart-authorization",
        {
            "session_id": "session-01",
            "target_config_sha256": "d" * 64,
            "restart_target_sha256": "1" * 64,
            "pre_probe_proof_sha256": "0" * 64,
            "process_before": "process-1",
            "accounts_sha256": "c" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
        },
        key_id="operator",
        private_key=keys["operator"],
    )
    with pytest.raises(ClosedError, match="out of phase"):
        await state.authorize_restart(authorization)
    assert not any(name.startswith("restart/") for name in await ledger.record_names())


@pytest.mark.asyncio
async def test_probe_marker_finishing_after_operation_deadline_is_refused() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(clock=clock, ledger=ledger, budget_ledger=memory_budget(), keyring=keyring)
    await ready_for_close(state, clock, keys)
    close_hash = await state.close_for_deny()
    await state.authorize_deny(deny_authorization(clock, keys, close_hash))
    signed = sign_object(
        "probe-authorization",
        {
            "session_id": "session-01",
            "phase": "pre-restart",
            "request_id": "probe-pre",
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
            "proof_expires_utc_ns": clock.utc_ns + 60_000_000_000,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(name: str, _payload: bytes) -> None:
        if name.startswith("probe/"):
            entered.set()
            await release.wait()

    ledger.before_create = hold
    task = asyncio.create_task(state.consume_probe("pre-restart", signed))
    await entered.wait()
    clock.advance(6_000_000_000)
    release.set()
    with pytest.raises(ClosedError, match="operation expiry"):
        await task
    assert state.phase is Phase.TERMINAL


async def ready_for_restart(  # noqa: PLR0913 -- independent timing faults need separate controls
    state: GatewayState,
    clock: FakeClock,
    keys: dict[str, Ed25519PrivateKey],
    *,
    arm_delay_ns: int = 0,
    started_offset_ns: int = 0,
    ingress_after_response_ns: int = 0,
    signing_delay_ns: int = 100_000_000,
    ingress_after_observation_ns: int = 0,
) -> bytes:
    await ready_for_close(state, clock, keys)
    close_hash = await state.close_for_deny()
    await state.authorize_deny(deny_authorization(clock, keys, close_hash))
    authorization = sign_object(
        "probe-authorization",
        {
            "session_id": "session-01",
            "phase": "pre-restart",
            "request_id": "probe-pre",
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
            "proof_expires_utc_ns": clock.utc_ns + 60_000_000_000,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    marker = await state.consume_probe("pre-restart", authorization)
    clock.advance(100_000_000)
    probe_started = clock.utc_ns + started_offset_ns
    clock.advance(100_000_000)
    ingress_started = clock.utc_ns
    clock.advance(100_000_000)
    response_observed = clock.utc_ns
    clock.advance(signing_delay_ns)
    if ingress_after_observation_ns:
        ingress_started = response_observed + ingress_after_observation_ns
    gateway = sign_object(
        "origin-probe-attestation",
        {
            "session_id": "session-01",
            "phase": "pre-restart",
            "origin_host": "isolated.example.internal",
            "status_code": 403,
            "tls_valid": True,
            "request_id": "probe-pre",
            "probe_marker_sha256": marker,
            "probe_started_utc_ns": probe_started,
            "probe_uncertainty_ns": clock.uncertainty_ns,
            "response_observed_utc_ns": response_observed,
            "response_uncertainty_ns": clock.uncertainty_ns,
            "response_sha256": "5" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="gateway",
        private_key=keys["gateway"],
    )
    if ingress_after_response_ns:
        clock.advance(ingress_after_response_ns)
        ingress_started = clock.utc_ns
    arm_observed = clock.utc_ns
    clock.advance(arm_delay_ns)
    proof = sign_object(
        "origin-probe-proof",
        {
            "session_id": "session-01",
            "phase": "pre-restart",
            "gateway_attestation_sha256": hashlib.sha256(gateway).hexdigest(),
            "request_id": "probe-pre",
            "probe_marker_sha256": marker,
            "authorization_sha256": hashlib.sha256(authorization).hexdigest(),
            "diagnostic_calibration_sha256": "e" * 64,
            "response_code_details": "direct_response",
            "upstream_request_attempt_count": 0,
            "app_log_absent": True,
            "app_logs_complete": True,
            "diagnostics_sha256": "a" * 64,
            "arm_state_sha256": "b" * 64,
            "diagnostics_observed_utc_ns": clock.utc_ns,
            "arm_observed_utc_ns": arm_observed,
            "ingress_started_utc_ns": ingress_started,
            "ingress_uncertainty_ns": clock.uncertainty_ns,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    await state.record_probe_result(gateway, proof)
    return proof


@pytest.mark.asyncio
async def test_stale_arm_observation_is_not_denial_proof() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    with pytest.raises(AuthorizationError, match="denial proof"):
        await ready_for_restart(state, clock, keys, arm_delay_ns=6_000_000_000)
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_probe_started_before_durable_marker_is_not_denial_proof() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    with pytest.raises(AuthorizationError, match="denial proof"):
        await ready_for_restart(state, clock, keys, started_offset_ns=-1_000_000_000)
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_ingress_start_after_gateway_response_is_not_denial_proof() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    with pytest.raises(AuthorizationError, match="denial proof"):
        await ready_for_restart(state, clock, keys, ingress_after_response_ns=3_000_000_000)
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_delayed_signing_does_not_hide_ingress_after_response() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    with pytest.raises(AuthorizationError, match="denial proof"):
        await ready_for_restart(
            state,
            clock,
            keys,
            signing_delay_ns=3_000_000_000,
            ingress_after_observation_ns=1_000_000_000,
        )


@pytest.mark.asyncio
async def test_health_observed_before_post_settlement_challenge_is_rejected() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    packet, allocation = signed_material(clock, keys)
    await state.arm(packet, allocation)
    await state.renew(sign_heartbeat(clock, keys, await state.issue_challenge()))
    for index in range(4):
        await complete_case(state, clock, keys, index)
    old_health_time = clock.utc_ns - 1_000_000_000
    challenge = await state.issue_pre_deny_health_challenge()
    clock.advance(100_000_000)
    health = sign_object(
        "pre-deny-health",
        {
            "session_id": "session-01",
            "origin_host": "isolated.example.internal",
            "status_code": 200,
            "tls_valid": True,
            "request_id": "old-health",
            "challenge": challenge,
            "issued_utc_ns": old_health_time,
        },
        key_id="gateway",
        private_key=keys["gateway"],
    )
    with pytest.raises(AuthorizationError, match="health attestation"):
        await state.record_pre_deny_health(health)


def restart_authorization(
    clock: FakeClock,
    keys: dict[str, Ed25519PrivateKey],
    proof: bytes,
) -> bytes:
    return sign_object(
        "restart-authorization",
        {
            "session_id": "session-01",
            "target_config_sha256": "d" * 64,
            "restart_target_sha256": "1" * 64,
            "pre_probe_proof_sha256": hashlib.sha256(proof).hexdigest(),
            "process_before": "process-1",
            "accounts_sha256": "c" * 64,
            "issued_utc_ns": clock.utc_ns,
            "expires_utc_ns": clock.utc_ns + 5_000_000_000,
        },
        key_id="operator",
        private_key=keys["operator"],
    )


@pytest.mark.asyncio
async def test_restart_marker_precedes_mutation_and_changed_accounts_are_rejected() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(clock=clock, ledger=ledger, budget_ledger=memory_budget(), keyring=keyring)
    proof = await ready_for_restart(state, clock, keys)
    marker = await state.authorize_restart(restart_authorization(clock, keys, proof))
    assert any(name.startswith("restart/") for name in await ledger.record_names())
    restart_nonce = await state.initiate_restart(
        marker, lambda _nonce: clock.advance(100_000_000) or True
    )
    start_proof = sign_object(
        "restart-start-proof",
        {
            "session_id": "session-01",
            "restart_marker_sha256": marker,
            "restart_target_sha256": "1" * 64,
            "operation_started_utc_ns": clock.utc_ns,
            "operation_uncertainty_ns": clock.uncertainty_ns,
            "initiation_nonce": restart_nonce,
            "evidence_sha256": "2" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    attestation = sign_object(
        "restart-attestation",
        {
            "session_id": "session-01",
            "process_before": "process-1",
            "process_after": "process-2",
            "restart_marker_sha256": marker,
            "pre_probe_proof_sha256": hashlib.sha256(proof).hexdigest(),
            "target_config_sha256": "d" * 64,
            "restart_target_sha256": "1" * 64,
            "start_proof_sha256": hashlib.sha256(start_proof).hexdigest(),
            "ready": True,
            "sole_worker": True,
            "accounts_sha256": "0" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="operator",
        private_key=keys["operator"],
    )
    with pytest.raises(AuthorizationError, match="restart attestation"):
        await state.record_restart(attestation, start_proof)
    assert state.phase is Phase.TERMINAL


@pytest.mark.asyncio
async def test_restart_marker_after_expiry_is_consumed_but_not_authorized() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    ledger = MemoryCreateOnlyLedger()
    state = GatewayState(clock=clock, ledger=ledger, budget_ledger=memory_budget(), keyring=keyring)
    proof = await ready_for_restart(state, clock, keys)
    signed = restart_authorization(clock, keys, proof)
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(name: str, _payload: bytes) -> None:
        if name.startswith("restart/"):
            entered.set()
            await release.wait()

    ledger.before_create = hold
    task = asyncio.create_task(state.authorize_restart(signed))
    await entered.wait()
    clock.advance(6_000_000_000)
    release.set()
    with pytest.raises(ClosedError, match="authorization expiry"):
        await task
    assert state.phase is Phase.TERMINAL
    assert any(name.startswith("restart/") for name in await ledger.record_names())


@pytest.mark.asyncio
async def test_restart_started_after_authorization_deadline_is_not_accepted() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    proof = await ready_for_restart(state, clock, keys)
    marker = await state.authorize_restart(restart_authorization(clock, keys, proof))
    restart_nonce = await state.initiate_restart(
        marker, lambda _nonce: clock.advance(100_000_000) or True
    )
    clock.advance(6_000_000_000)
    start = sign_object(
        "restart-start-proof",
        {
            "session_id": "session-01",
            "restart_marker_sha256": marker,
            "restart_target_sha256": "1" * 64,
            "operation_started_utc_ns": clock.utc_ns,
            "operation_uncertainty_ns": clock.uncertainty_ns,
            "initiation_nonce": restart_nonce,
            "evidence_sha256": "2" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    completed = sign_object(
        "restart-attestation",
        {
            "session_id": "session-01",
            "process_before": "process-1",
            "process_after": "process-2",
            "restart_marker_sha256": marker,
            "pre_probe_proof_sha256": hashlib.sha256(proof).hexdigest(),
            "target_config_sha256": "d" * 64,
            "restart_target_sha256": "1" * 64,
            "start_proof_sha256": hashlib.sha256(start).hexdigest(),
            "ready": True,
            "sole_worker": True,
            "accounts_sha256": "c" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="operator",
        private_key=keys["operator"],
    )
    with pytest.raises(AuthorizationError, match="restart attestation"):
        await state.record_restart(completed, start)


@pytest.mark.asyncio
async def test_restart_proof_before_initiation_is_rejected() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    proof = await ready_for_restart(state, clock, keys)
    marker = await state.authorize_restart(restart_authorization(clock, keys, proof))
    nonce = await state.initiate_restart(marker, lambda _nonce: clock.advance(100_000_000) or True)
    start = sign_object(
        "restart-start-proof",
        {
            "session_id": "session-01",
            "restart_marker_sha256": marker,
            "restart_target_sha256": "1" * 64,
            "initiation_nonce": nonce,
            "operation_started_utc_ns": clock.utc_ns - 1_000_000_000,
            "operation_uncertainty_ns": clock.uncertainty_ns,
            "evidence_sha256": "2" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="financial-verifier",
        private_key=keys["financial-verifier"],
    )
    completed = sign_object(
        "restart-attestation",
        {
            "session_id": "session-01",
            "process_before": "process-1",
            "process_after": "process-2",
            "restart_marker_sha256": marker,
            "pre_probe_proof_sha256": hashlib.sha256(proof).hexdigest(),
            "target_config_sha256": "d" * 64,
            "restart_target_sha256": "1" * 64,
            "start_proof_sha256": hashlib.sha256(start).hexdigest(),
            "ready": True,
            "sole_worker": True,
            "accounts_sha256": "c" * 64,
            "issued_utc_ns": clock.utc_ns,
        },
        key_id="operator",
        private_key=keys["operator"],
    )
    with pytest.raises(AuthorizationError, match="restart attestation"):
        await state.record_restart(completed, start)


@pytest.mark.asyncio
async def test_restart_initiation_after_expiry_never_calls_operator() -> None:
    clock = FakeClock()
    keys, keyring = signed_keys()
    state = GatewayState(
        clock=clock, ledger=MemoryCreateOnlyLedger(), budget_ledger=memory_budget(), keyring=keyring
    )
    proof = await ready_for_restart(state, clock, keys)
    marker = await state.authorize_restart(restart_authorization(clock, keys, proof))
    clock.advance(6_000_000_000)
    calls: list[bool] = []
    with pytest.raises(ClosedError, match="expired or not authorized"):
        await state.initiate_restart(marker, lambda _nonce: calls.append(True) or True)
    assert not calls
