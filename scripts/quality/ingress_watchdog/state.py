"""Fail-closed, single-session gateway authorization state machine."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .clock import MAX_CLOCK_UNCERTAINTY_NS, Clock, ClockSample
from .errors import AuthorizationError, ClockError, ClosedError, ProtocolError
from .ledger import LedgerKind
from .schema import canonical_json, parse_canonical_json, require_exact_keys
from .signing import KeyRole, VerificationKey, verify_object

if TYPE_CHECKING:
    from collections.abc import Callable

    from .ledger import CreateOnlyLedger

MAX_PACKET_LIFETIME_NS = 30 * 60 * 1_000_000_000
MAX_HEARTBEAT_AGE_NS = 3 * 1_000_000_000
MAX_RECEIPT_AGE_NS = 5 * 1_000_000_000
MAX_OUTPUT_TOKENS = 128
MAX_INPUT_TOKENS = 64
MAX_TOTAL_RESERVE_MICRO_USD = 1_000_000
MAX_REQUEST_BYTES = 1_048_576
MAX_G1_INPUT_BYTES = 4096
MAX_LEASE_TTL_NS = 15 * 1_000_000_000
MAX_PROCESS_ID = 2_147_483_647
MAX_ALLOCATION_AGE_NS = 30 * 60 * 1_000_000_000
MIN_AUDIT_WINDOW_NS = 86_400_000_000_000
MAX_CASES = 4
REQUIRED_DEPLOYMENTS = 2
CASES_PER_DEPLOYMENT = 2
STREAM_VARIANTS = frozenset((False, True))
TLS_PORT = 443
MAX_DNS_NAME_LENGTH = 253
MIN_DNS_LABELS = 2
MIN_HTTP_STATUS = 100
MAX_HTTP_STATUS = 599
HTTP_OK = 200
HTTP_DENIED = 403
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,96}$")
_PROCESS_START_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_ALLOWED_ROUTES = (
    {"method": "GET", "path": "/health/ready"},
    {"method": "GET", "path": "/admin/status"},
    {"method": "POST", "path": "/openai/v1/responses"},
)


class Phase(StrEnum):
    CLOSED = "closed"
    ARMING = "arming"
    ARMED = "armed"
    ACTIVE = "active"
    CASE_PENDING = "case_pending"
    CLOSING = "closing"
    DENY_PROBES = "deny_probes"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class CaseSpec:
    case_id: str
    order: int
    deployment_id: str
    body_sha256: str
    model: str
    stream: bool
    max_input_tokens: int
    max_output_tokens: int
    reserve_microusd: int


@dataclass(frozen=True, slots=True)
class Packet:
    session_id: str
    not_after_utc_ns: int
    origin_host: str
    origin_port: int
    runner_identity_sha256: str
    gateway_certificate_sha256: str
    reviewer_key_id: str
    budget_authority_key_id: str
    supervisor_key_id: str
    financial_verifier_key_id: str
    gateway_key_id: str
    operator_key_id: str
    max_request_bytes: int
    lease_ttl_ns: int
    allocation_id: str
    allocation_sha256: str
    budget_namespace_sha256: str
    config_sha256: str
    expected_deny_state_sha256: str
    restart_target_sha256: str
    baseline_state_sha256: str
    baseline_accounts_sha256: str
    baseline_process_id: str
    denial_response_code_details: str
    diagnostic_calibration_sha256: str
    aggregate_reserve_microusd: int
    cases: tuple[CaseSpec, ...]
    raw_sha256: str

    @classmethod
    def parse(cls, payload: dict[str, object], *, raw_sha256: str) -> Packet:
        fields = {
            "packet_version",
            "session_id",
            "not_after_utc_ns",
            "origin_host",
            "origin_port",
            "runner_identity_sha256",
            "gateway_certificate_sha256",
            "reviewer_key_id",
            "budget_authority_key_id",
            "supervisor_key_id",
            "financial_verifier_key_id",
            "gateway_key_id",
            "operator_key_id",
            "max_request_bytes",
            "lease_ttl_ns",
            "allocation_id",
            "allocation_sha256",
            "budget_namespace_sha256",
            "config_sha256",
            "expected_deny_state_sha256",
            "restart_target_sha256",
            "baseline_state_sha256",
            "baseline_accounts_sha256",
            "baseline_process_id",
            "denial_response_code_details",
            "diagnostic_calibration_sha256",
            "aggregate_reserve_microusd",
            "routes",
            "cases",
        }
        data = require_exact_keys(payload, fields, label="packet")
        if data["packet_version"] != 1:
            raise ProtocolError("unsupported packet version")
        session_id = _identifier(data["session_id"], "session_id")
        not_after = _integer(data["not_after_utc_ns"], "not_after_utc_ns", minimum=1)
        origin_host = _hostname(data["origin_host"])
        origin_port = _integer(data["origin_port"], "origin_port", minimum=1, maximum=65535)
        if origin_port != TLS_PORT:
            raise ProtocolError("only TLS origin port 443 is permitted")
        runner_identity = _digest(data["runner_identity_sha256"], "runner identity")
        gateway_certificate = _digest(
            data["gateway_certificate_sha256"],
            "gateway client certificate",
        )
        reviewer_key_id = _identifier(data["reviewer_key_id"], "reviewer_key_id")
        budget_authority_key_id = _identifier(
            data["budget_authority_key_id"], "budget_authority_key_id"
        )
        supervisor_key_id = _identifier(data["supervisor_key_id"], "supervisor_key_id")
        financial_verifier_key_id = _identifier(
            data["financial_verifier_key_id"], "financial_verifier_key_id"
        )
        gateway_key_id = _identifier(data["gateway_key_id"], "gateway_key_id")
        operator_key_id = _identifier(data["operator_key_id"], "operator_key_id")
        max_request_bytes = _integer(
            data["max_request_bytes"], "max_request_bytes", minimum=1, maximum=MAX_REQUEST_BYTES
        )
        lease_ttl_ns = _integer(
            data["lease_ttl_ns"], "lease_ttl_ns", minimum=1, maximum=MAX_LEASE_TTL_NS
        )
        allocation_id = _identifier(data["allocation_id"], "allocation_id")
        allocation_sha256 = _digest(data["allocation_sha256"], "allocation")
        budget_namespace_sha256 = _digest(data["budget_namespace_sha256"], "budget namespace")
        config_sha256 = _digest(data["config_sha256"], "configuration")
        expected_deny_state_sha256 = _digest(data["expected_deny_state_sha256"], "DENY state")
        restart_target_sha256 = _digest(data["restart_target_sha256"], "restart target")
        baseline_state_sha256 = _digest(data["baseline_state_sha256"], "baseline state")
        baseline_accounts_sha256 = _digest(data["baseline_accounts_sha256"], "baseline accounts")
        baseline_process_id = _identifier(data["baseline_process_id"], "baseline process")
        denial_details = data["denial_response_code_details"]
        if (
            not isinstance(denial_details, str)
            or not denial_details.isascii()
            or not denial_details
        ):
            raise ProtocolError("calibrated denial details are required")
        calibration_digest = _digest(
            data["diagnostic_calibration_sha256"], "diagnostic calibration"
        )
        aggregate_reserve = _integer(
            data["aggregate_reserve_microusd"],
            "aggregate_reserve_microusd",
            minimum=1,
            maximum=MAX_TOTAL_RESERVE_MICRO_USD,
        )
        if data["routes"] != list(_ALLOWED_ROUTES):
            raise ProtocolError("packet route set is not the fixed approved set")
        cases = _parse_cases(data["cases"], aggregate_reserve)
        return cls(
            session_id=session_id,
            not_after_utc_ns=not_after,
            origin_host=origin_host,
            origin_port=origin_port,
            runner_identity_sha256=runner_identity,
            gateway_certificate_sha256=gateway_certificate,
            reviewer_key_id=reviewer_key_id,
            budget_authority_key_id=budget_authority_key_id,
            supervisor_key_id=supervisor_key_id,
            financial_verifier_key_id=financial_verifier_key_id,
            gateway_key_id=gateway_key_id,
            operator_key_id=operator_key_id,
            max_request_bytes=max_request_bytes,
            lease_ttl_ns=lease_ttl_ns,
            allocation_id=allocation_id,
            allocation_sha256=allocation_sha256,
            budget_namespace_sha256=budget_namespace_sha256,
            config_sha256=config_sha256,
            expected_deny_state_sha256=expected_deny_state_sha256,
            restart_target_sha256=restart_target_sha256,
            baseline_state_sha256=baseline_state_sha256,
            baseline_accounts_sha256=baseline_accounts_sha256,
            baseline_process_id=baseline_process_id,
            denial_response_code_details=denial_details,
            diagnostic_calibration_sha256=calibration_digest,
            aggregate_reserve_microusd=aggregate_reserve,
            cases=cases,
            raw_sha256=raw_sha256,
        )


@dataclass(frozen=True, slots=True)
class DispatchPermit:
    session_id: str
    case_id: str
    body_sha256: str
    record_sha256: str
    token: str
    prepared_utc_ns: int
    prepared_uncertainty_ns: int


@dataclass(frozen=True, slots=True)
class TrustedBudgetBinding:
    program_scope_sha256: str
    namespace: str
    registry_namespace: str
    funding_cycle_end_utc_ns: int
    financial_retain_until_utc_ns: int
    authority_key_id: str
    signed_binding: bytes
    registry_reviewer_key_id: str
    signed_registry_binding: bytes


def _integer(value: object, label: str, *, minimum: int, maximum: int = 2**63 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ProtocolError(f"{label} is out of bounds")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ProtocolError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ProtocolError(f"{label} digest is invalid")
    return value


def _hostname(value: object) -> str:
    if not isinstance(value, str) or not value.isascii() or value != value.lower():
        raise ProtocolError("origin host must be lowercase ASCII DNS")
    if len(value) > MAX_DNS_NAME_LENGTH or value.endswith("."):
        raise ProtocolError("origin host is invalid")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ProtocolError("origin must be a DNS name, not an IP literal")
    labels = value.split(".")
    if len(labels) < MIN_DNS_LABELS or any(not _DNS_LABEL.fullmatch(label) for label in labels):
        raise ProtocolError("origin host is not a valid DNS name")
    return value


def _unique_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate request field")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ProtocolError("non-finite request number")


def _validate_case_body(body: bytes, case: CaseSpec) -> None:
    try:
        request = json.loads(
            body, object_pairs_hook=_unique_json_pairs, parse_constant=_reject_json_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ProtocolError("approved request body is not valid JSON") from exc
    if not isinstance(request, dict):
        raise ProtocolError("approved request body is not an object")
    if set(request) != {"model", "stream", "max_output_tokens", "input"}:
        raise AuthorizationError("request is not the approved stateless text shape")
    text = request.get("input")
    output_limit = request.get("max_output_tokens")
    if (
        request.get("model") != case.model
        or request.get("stream") is not case.stream
        or not isinstance(text, str)
        or not text
        or len(text.encode("utf-8")) > MAX_G1_INPUT_BYTES
        or isinstance(output_limit, bool)
        or not isinstance(output_limit, int)
        or output_limit != case.max_output_tokens
    ):
        raise AuthorizationError("request semantics do not match the approved case")


def _parse_cases(value: object, aggregate_reserve: int) -> tuple[CaseSpec, ...]:
    if not isinstance(value, list) or len(value) != MAX_CASES:
        raise ProtocolError("packet must contain exactly four ordered cases")
    required = {
        "case_id",
        "order",
        "deployment_id",
        "body_sha256",
        "model",
        "stream",
        "max_input_tokens",
        "max_output_tokens",
        "reserve_microusd",
    }
    cases: list[CaseSpec] = []
    for expected_order, item in enumerate(value):
        data = require_exact_keys(item, required, label="case")
        case_id = _identifier(data["case_id"], "case_id")
        order = _integer(data["order"], "case order", minimum=0, maximum=3)
        if order != expected_order:
            raise ProtocolError("case order is not contiguous")
        deployment_id = _identifier(data["deployment_id"], "deployment_id")
        body_hash = _digest(data["body_sha256"], "case body")
        model = _identifier(data["model"], "model")
        stream = data["stream"]
        if not isinstance(stream, bool):
            raise ProtocolError("stream must be boolean")
        max_input_tokens = _integer(
            data["max_input_tokens"],
            "max_input_tokens",
            minimum=1,
            maximum=MAX_INPUT_TOKENS,
        )
        max_output = _integer(
            data["max_output_tokens"], "max_output_tokens", minimum=1, maximum=MAX_OUTPUT_TOKENS
        )
        reserve = _integer(data["reserve_microusd"], "reserve_microusd", minimum=1)
        cases.append(
            CaseSpec(
                case_id=case_id,
                order=order,
                deployment_id=deployment_id,
                body_sha256=body_hash,
                model=model,
                stream=stream,
                max_input_tokens=max_input_tokens,
                max_output_tokens=max_output,
                reserve_microusd=reserve,
            )
        )
    if len({case.case_id for case in cases}) != MAX_CASES:
        raise ProtocolError("case IDs must be unique")
    deployments = {case.deployment_id for case in cases}
    if len(deployments) != REQUIRED_DEPLOYMENTS:
        raise ProtocolError("the four cases must use two distinct deployments")
    if sum(case.reserve_microusd for case in cases) > aggregate_reserve:
        raise ProtocolError("case reserves exceed the aggregate reserve")
    for deployment_id in deployments:
        pair = [case for case in cases if case.deployment_id == deployment_id]
        if len(pair) != CASES_PER_DEPLOYMENT or {case.stream for case in pair} != STREAM_VARIANTS:
            raise ProtocolError("each deployment must have one nonstream and one stream case")
    return tuple(cases)


def _validate_allocation(
    allocation: dict[str, object],
    *,
    packet: Packet,
    signed_allocation_sha256: str,
    sample: ClockSample,
    binding: TrustedBudgetBinding,
) -> None:
    data = require_exact_keys(
        allocation,
        {
            "allocation_id",
            "session_id",
            "program_scope_sha256",
            "budget_namespace_sha256",
            "prior_liabilities_sha256",
            "funding_cycle_end_utc_ns",
            "audit_retain_until_utc_ns",
            "aggregate_limit_microusd",
            "prior_liability_microusd",
            "aggregate_attempt_limit",
            "prior_attempts",
            "case_ids",
            "reserves_microusd",
            "issued_utc_ns",
        },
        label="program allocation",
    )
    limit = _integer(
        data["aggregate_limit_microusd"],
        "aggregate_limit_microusd",
        minimum=1,
        maximum=MAX_TOTAL_RESERVE_MICRO_USD,
    )
    prior_liability = _integer(
        data["prior_liability_microusd"],
        "prior_liability_microusd",
        minimum=0,
        maximum=limit,
    )
    attempt_limit = _integer(
        data["aggregate_attempt_limit"],
        "aggregate_attempt_limit",
        minimum=MAX_CASES,
        maximum=16,
    )
    prior_attempts = _integer(
        data["prior_attempts"],
        "prior_attempts",
        minimum=0,
        maximum=attempt_limit - MAX_CASES,
    )
    issued_utc_ns = _integer(data["issued_utc_ns"], "allocation issue time", minimum=1)
    scope = _digest(data["program_scope_sha256"], "program scope")
    _digest(data["prior_liabilities_sha256"], "prior liabilities")
    case_ids = [case.case_id for case in packet.cases]
    reserves = [case.reserve_microusd for case in packet.cases]
    allocation_reserves = data["reserves_microusd"]
    allocation_case_ids = data["case_ids"]
    if (
        not isinstance(allocation_case_ids, list)
        or not isinstance(allocation_reserves, list)
        or data["allocation_id"] != packet.allocation_id
        or data["session_id"] != packet.session_id
        or scope != binding.program_scope_sha256
        or data["budget_namespace_sha256"] != packet.budget_namespace_sha256
        or data["funding_cycle_end_utc_ns"] != binding.funding_cycle_end_utc_ns
        or data["audit_retain_until_utc_ns"] != binding.financial_retain_until_utc_ns
        or issued_utc_ns > sample.utc_ns + sample.uncertainty_ns
        or sample.utc_ns - issued_utc_ns > MAX_ALLOCATION_AGE_NS
        or issued_utc_ns >= packet.not_after_utc_ns
        or data["case_ids"] != case_ids
        or allocation_reserves != reserves
        or signed_allocation_sha256 != packet.allocation_sha256
        or prior_liability + sum(reserves) > limit
        or packet.aggregate_reserve_microusd != sum(reserves)
        or prior_attempts + MAX_CASES > attempt_limit
    ):
        raise AuthorizationError("program allocation does not match packet or aggregate limits")


class GatewayState:
    """Single-process fail-closed authorization state.

    Every ambiguous durable transition is terminal. A new process starts closed;
    its ledger will reject replay of a previously consumed arm/session ID.
    """

    def __init__(  # noqa: PLR0913, PLR0915 -- independent attested bindings are mandatory
        self,
        *,
        clock: Clock,
        ledger: CreateOnlyLedger,
        budget_ledger: CreateOnlyLedger,
        registry_ledger: CreateOnlyLedger,
        keyring: dict[str, VerificationKey],
        budget_binding: TrustedBudgetBinding,
    ) -> None:
        scope = _digest(budget_binding.program_scope_sha256, "trusted program scope")
        expected_financial_retain_until_utc_ns = budget_binding.financial_retain_until_utc_ns
        if (
            ledger.kind is not LedgerKind.SESSION
            or budget_ledger.kind is not LedgerKind.BUDGET
            or registry_ledger.kind is not LedgerKind.REGISTRY
            or not budget_binding.namespace
            or not budget_binding.registry_namespace
            or budget_ledger.namespace != budget_binding.namespace
            or registry_ledger.namespace != budget_binding.registry_namespace
            or ledger.namespace == budget_ledger.namespace
            or registry_ledger.namespace in {ledger.namespace, budget_ledger.namespace}
            or budget_ledger.program_scope_sha256 != scope
            or registry_ledger.program_scope_sha256 != scope
            or budget_ledger.financial_retain_until_utc_ns != expected_financial_retain_until_utc_ns
            or registry_ledger.financial_retain_until_utc_ns
            != expected_financial_retain_until_utc_ns
            or isinstance(expected_financial_retain_until_utc_ns, bool)
            or not isinstance(expected_financial_retain_until_utc_ns, int)
            or expected_financial_retain_until_utc_ns <= 0
            or isinstance(budget_binding.funding_cycle_end_utc_ns, bool)
            or not isinstance(budget_binding.funding_cycle_end_utc_ns, int)
            or budget_binding.funding_cycle_end_utc_ns <= 0
            or expected_financial_retain_until_utc_ns
            < budget_binding.funding_cycle_end_utc_ns + MIN_AUDIT_WINDOW_NS
        ):
            raise AuthorizationError("independent ledger bindings are invalid")
        binding_data = require_exact_keys(
            verify_object(
                budget_binding.signed_binding,
                expected_kind="budget-namespace-binding",
                expected_role=KeyRole.BUDGET_AUTHORITY,
                keyring=keyring,
                expected_key_id=budget_binding.authority_key_id,
            ),
            {
                "program_scope_sha256",
                "budget_namespace_sha256",
                "registry_namespace_sha256",
                "funding_cycle_end_utc_ns",
                "audit_retain_until_utc_ns",
                "issued_utc_ns",
                "expires_utc_ns",
            },
            label="budget namespace binding",
        )
        registry_data = require_exact_keys(
            verify_object(
                budget_binding.signed_registry_binding,
                expected_kind="trusted-registry-binding",
                expected_role=KeyRole.REVIEWER,
                keyring=keyring,
                expected_key_id=budget_binding.registry_reviewer_key_id,
            ),
            {
                "program_scope_sha256",
                "registry_namespace_sha256",
                "issued_utc_ns",
                "expires_utc_ns",
            },
            label="independently pinned registry binding",
        )
        sample = clock.sample()
        binding_issued = _integer(binding_data["issued_utc_ns"], "binding issue time", minimum=1)
        binding_expires = _integer(binding_data["expires_utc_ns"], "binding expiry", minimum=1)
        registry_issued = _integer(registry_data["issued_utc_ns"], "registry issue time", minimum=1)
        registry_expires = _integer(registry_data["expires_utc_ns"], "registry expiry", minimum=1)
        if (
            not sample.trusted
            or not 0 <= sample.uncertainty_ns <= MAX_CLOCK_UNCERTAINTY_NS
            or binding_data["program_scope_sha256"] != scope
            or binding_data["budget_namespace_sha256"]
            != hashlib.sha256(budget_binding.namespace.encode()).hexdigest()
            or binding_data["registry_namespace_sha256"]
            != hashlib.sha256(budget_binding.registry_namespace.encode()).hexdigest()
            or binding_data["funding_cycle_end_utc_ns"] != budget_binding.funding_cycle_end_utc_ns
            or binding_data["audit_retain_until_utc_ns"] != expected_financial_retain_until_utc_ns
            or binding_issued > sample.utc_ns + sample.uncertainty_ns
            or binding_expires <= sample.utc_ns + sample.uncertainty_ns
            or binding_expires <= binding_issued
            or registry_data["program_scope_sha256"] != scope
            or registry_data["registry_namespace_sha256"]
            != hashlib.sha256(budget_binding.registry_namespace.encode()).hexdigest()
            or registry_issued > sample.utc_ns + sample.uncertainty_ns
            or registry_expires <= sample.utc_ns + sample.uncertainty_ns
            or registry_expires <= registry_issued
        ):
            raise AuthorizationError("signed budget namespace binding is invalid or expired")
        self._clock = clock
        self._ledger = ledger
        self._budget_ledger = budget_ledger
        self._registry_ledger = registry_ledger
        self._budget_binding = budget_binding
        self._binding_expires_utc_ns = min(binding_expires, registry_expires)
        self._keyring = keyring
        self._program_scope_sha256 = scope
        self._budget_namespace_sha256 = hashlib.sha256(
            budget_binding.namespace.encode()
        ).hexdigest()
        self._financial_retain_until_utc_ns = expected_financial_retain_until_utc_ns
        self._lock = asyncio.Lock()
        self._phase = Phase.CLOSED
        self._packet: Packet | None = None
        self._last_sample: ClockSample | None = None
        self._challenge: str | None = None
        self._lease_expires_boottime_ns = 0
        self._next_case = 0
        self._pending: DispatchPermit | None = None
        self._dispatched: DispatchPermit | None = None
        self._transition = 0
        self._probes: set[str] = set()
        self._verified_probes: set[str] = set()
        self._probe_context: dict[str, tuple[str, str, str, int, int, int, int, int]] = {}
        self._probe_proof_hashes: dict[str, str] = {}
        self._restart_verified = False
        self._restart_marker_sha256: str | None = None
        self._restart_authorization_expires_utc_ns: int | None = None
        self._restart_marker_ready_utc_ns: int | None = None
        self._restart_initiated = False
        self._restart_initiated_at_utc_ns: int | None = None
        self._restart_initiated_uncertainty_ns: int | None = None
        self._restart_initiation_nonce: str | None = None
        self._pre_deny_health_sha256: str | None = None
        self._pre_deny_health_issued_utc_ns: int | None = None
        self._pre_deny_challenge: str | None = None
        self._pre_deny_challenge_issued_utc_ns: int | None = None
        self._pre_deny_challenge_uncertainty_ns: int | None = None
        self._close_sha256: str | None = None
        self._deny_authorized = False
        self._deny_authorizing = False
        self._last_state_sha256: str | None = None
        self._last_accounts_sha256: str | None = None
        self._last_process: str | None = None

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def next_case_id(self) -> str | None:
        if self._packet is None or self._next_case >= len(self._packet.cases):
            return None
        return self._packet.cases[self._next_case].case_id

    def _sample(self) -> ClockSample:
        sample = self._clock.sample()
        if (
            not sample.trusted
            or sample.uncertainty_ns < 0
            or sample.uncertainty_ns > MAX_CLOCK_UNCERTAINTY_NS
        ):
            raise ClockError("clock trust or uncertainty is outside the approved bound")
        prior = self._last_sample
        if prior is not None:
            boot_delta = sample.boottime_ns - prior.boottime_ns
            monotonic_delta = sample.monotonic_ns - prior.monotonic_ns
            utc_delta = sample.utc_ns - prior.utc_ns
            if boot_delta < 0 or monotonic_delta < 0:
                raise ClockError("boot or monotonic clock moved backwards")
            suspend_delta = boot_delta - monotonic_delta
            if suspend_delta > MAX_CLOCK_UNCERTAINTY_NS:
                raise ClockError("host suspension detected; session is terminal")
            if abs(utc_delta - boot_delta) > (
                sample.uncertainty_ns + prior.uncertainty_ns + 100_000_000
            ):
                raise ClockError("trusted UTC and boot clocks disagree")
        self._last_sample = sample
        return sample

    def _check_live(self, sample: ClockSample) -> None:
        packet = self._packet
        if packet is None:
            raise ClosedError("no packet is armed")
        if sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns:
            raise ClosedError("signed absolute deadline has expired")
        if sample.boottime_ns >= self._lease_expires_boottime_ns:
            raise ClosedError("lease has expired")
        if self._phase not in {Phase.ACTIVE, Phase.CASE_PENDING}:
            raise ClosedError("gateway is not in an active forwarding phase")

    def _mark_terminal(self) -> None:
        self._transition += 1
        self._phase = Phase.TERMINAL
        self._challenge = None

    async def _terminal(self) -> None:
        async with self._lock:
            self._mark_terminal()

    async def arm(  # noqa: PLR0915 -- ordered durable fences remain explicit
        self, signed_packet: bytes, signed_allocation: bytes
    ) -> Packet:
        try:
            untrusted_envelope = require_exact_keys(
                parse_canonical_json(signed_packet),
                {"kind", "key_id", "payload", "signature"},
                label="signed packet",
            )
            untrusted_payload = untrusted_envelope["payload"]
            if not isinstance(untrusted_payload, dict):
                raise ProtocolError("signed packet payload must be an object")
            packet_reviewer_id = _identifier(
                untrusted_payload.get("reviewer_key_id"),
                "reviewer_key_id",
            )
            payload = verify_object(
                signed_packet,
                expected_kind="packet",
                expected_role=KeyRole.REVIEWER,
                keyring=self._keyring,
                expected_key_id=packet_reviewer_id,
            )
            packet = Packet.parse(
                payload,
                raw_sha256=hashlib.sha256(signed_packet).hexdigest(),
            )
            if packet.budget_namespace_sha256 != self._budget_namespace_sha256:
                raise AuthorizationError(
                    "packet budget namespace does not match trusted configuration"
                )
            allocation = verify_object(
                signed_allocation,
                expected_kind="program-allocation",
                expected_role=KeyRole.BUDGET_AUTHORITY,
                keyring=self._keyring,
                expected_key_id=packet.budget_authority_key_id,
            )
            sample = self._sample()
            _validate_allocation(
                allocation,
                packet=packet,
                signed_allocation_sha256=hashlib.sha256(signed_allocation).hexdigest(),
                sample=sample,
                binding=self._budget_binding,
            )
            if (
                packet.not_after_utc_ns <= sample.utc_ns + sample.uncertainty_ns
                or packet.not_after_utc_ns - sample.utc_ns > MAX_PACKET_LIFETIME_NS
                or self._financial_retain_until_utc_ns <= packet.not_after_utc_ns
                or self._budget_binding.funding_cycle_end_utc_ns <= packet.not_after_utc_ns
                or self._binding_expires_utc_ns < packet.not_after_utc_ns
            ):
                raise ProtocolError("packet deadline is expired or exceeds 30 minutes")
            async with self._lock:
                if self._phase is not Phase.CLOSED:
                    raise ClosedError("gateway can arm only once per process")
                self._phase = Phase.ARMING
                self._packet = packet
                self._last_state_sha256 = packet.baseline_state_sha256
                self._last_accounts_sha256 = packet.baseline_accounts_sha256
                self._last_process = packet.baseline_process_id
                self._transition += 1
                transition = self._transition
            allocation_record = canonical_json(
                {
                    "allocation_id": packet.allocation_id,
                    "allocation_sha256": packet.allocation_sha256,
                    "session_id": packet.session_id,
                    "signed_allocation_sha256": hashlib.sha256(signed_allocation).hexdigest(),
                }
            )
            await self._registry_ledger.create(
                self._budget_record_name("program", self._program_scope_sha256),
                allocation_record,
            )
            async with self._lock:
                sample = self._sample()
                if (
                    self._transition != transition
                    or self._phase is not Phase.ARMING
                    or sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                ):
                    raise ClosedError("allocation completed after closure or expiry")
            await self._budget_ledger.create(
                self._budget_record_name("program", self._program_scope_sha256),
                allocation_record,
            )
            async with self._lock:
                sample = self._sample()
                if (
                    self._transition != transition
                    or self._phase is not Phase.ARMING
                    or sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                ):
                    raise ClosedError("budget fence completed after closure or expiry")
            record = canonical_json(
                {
                    "packet_sha256": packet.raw_sha256,
                    "session_id": packet.session_id,
                    "not_after_utc_ns": packet.not_after_utc_ns,
                }
            )
            record_hash = await self._ledger.create(
                self._record_name(packet.session_id, "arm", packet.session_id),
                record,
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.ARMING:
                    raise ClosedError("arm completed after the session was closed")
                sample = self._sample()
                if sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns:
                    raise ClosedError("arm completed after the packet deadline")
                self._phase = Phase.ARMED
                self._lease_expires_boottime_ns = 0
                self._last_sample = sample
                del record_hash
            return packet
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def record_probe_result(
        self,
        signed_gateway_attestation: bytes,
        signed_verifier_proof: bytes,
    ) -> None:
        """Bind ACA-origin evidence to calibrated independent diagnostic evidence."""
        try:
            gateway_data = verify_object(
                signed_gateway_attestation,
                expected_kind="origin-probe-attestation",
                expected_role=KeyRole.GATEWAY,
                keyring=self._keyring,
                expected_key_id=self._packet.gateway_key_id if self._packet is not None else None,
            )
            verifier_data = verify_object(
                signed_verifier_proof,
                expected_kind="origin-probe-proof",
                expected_role=KeyRole.FINANCIAL_VERIFIER,
                keyring=self._keyring,
                expected_key_id=(
                    self._packet.financial_verifier_key_id if self._packet is not None else None
                ),
            )
            gateway = require_exact_keys(
                gateway_data,
                {
                    "session_id",
                    "phase",
                    "origin_host",
                    "status_code",
                    "tls_valid",
                    "request_id",
                    "probe_marker_sha256",
                    "probe_started_utc_ns",
                    "probe_uncertainty_ns",
                    "response_observed_utc_ns",
                    "response_uncertainty_ns",
                    "response_sha256",
                    "issued_utc_ns",
                },
                label="gateway origin probe",
            )
            proof = require_exact_keys(
                verifier_data,
                {
                    "session_id",
                    "phase",
                    "gateway_attestation_sha256",
                    "request_id",
                    "probe_marker_sha256",
                    "authorization_sha256",
                    "diagnostic_calibration_sha256",
                    "response_code_details",
                    "upstream_request_attempt_count",
                    "app_log_absent",
                    "app_logs_complete",
                    "diagnostics_sha256",
                    "arm_state_sha256",
                    "diagnostics_observed_utc_ns",
                    "arm_observed_utc_ns",
                    "ingress_started_utc_ns",
                    "ingress_uncertainty_ns",
                    "issued_utc_ns",
                },
                label="verifier origin probe proof",
            )
            async with self._lock:
                sample = self._sample()
                packet = self._packet
                phase = gateway["phase"]
                if (
                    packet is None
                    or self._phase is not Phase.DENY_PROBES
                    or not isinstance(phase, str)
                    or phase not in self._probes
                    or phase in self._verified_probes
                ):
                    raise ClosedError("origin probe result is out of phase")
                gateway_issued = _integer(gateway["issued_utc_ns"], "gateway probe time", minimum=1)
                proof_issued = _integer(proof["issued_utc_ns"], "verifier proof time", minimum=1)
                diagnostic_time = _integer(
                    proof["diagnostics_observed_utc_ns"], "diagnostic time", minimum=1
                )
                arm_time = _integer(proof["arm_observed_utc_ns"], "ARM observation time", minimum=1)
                probe_started = _integer(gateway["probe_started_utc_ns"], "probe start", minimum=1)
                probe_uncertainty = _integer(
                    gateway["probe_uncertainty_ns"],
                    "probe uncertainty",
                    minimum=0,
                    maximum=MAX_CLOCK_UNCERTAINTY_NS,
                )
                response_observed = _integer(
                    gateway["response_observed_utc_ns"], "response observation", minimum=1
                )
                response_uncertainty = _integer(
                    gateway["response_uncertainty_ns"],
                    "response uncertainty",
                    minimum=0,
                    maximum=MAX_CLOCK_UNCERTAINTY_NS,
                )
                ingress_started = _integer(
                    proof["ingress_started_utc_ns"], "ingress start", minimum=1
                )
                ingress_uncertainty = _integer(
                    proof["ingress_uncertainty_ns"],
                    "ingress uncertainty",
                    minimum=0,
                    maximum=MAX_CLOCK_UNCERTAINTY_NS,
                )
                (
                    marker,
                    authorization,
                    request_id,
                    auth_issued,
                    probe_expires,
                    proof_expires,
                    marker_ready,
                    marker_uncertainty,
                ) = self._probe_context[phase]
                _identifier(gateway["request_id"], "gateway probe request ID")
                upstream_attempts = _integer(
                    proof["upstream_request_attempt_count"],
                    "upstream request attempts",
                    minimum=0,
                    maximum=0,
                )
                if (
                    gateway["session_id"] != packet.session_id
                    or proof["session_id"] != packet.session_id
                    or proof["phase"] != phase
                    or gateway["origin_host"] != packet.origin_host
                    or gateway["status_code"] != HTTP_DENIED
                    or gateway["tls_valid"] is not True
                    or gateway["request_id"] != proof["request_id"]
                    or gateway["request_id"] != request_id
                    or gateway["probe_marker_sha256"] != marker
                    or proof["probe_marker_sha256"] != marker
                    or proof["authorization_sha256"] != authorization
                    or proof["diagnostic_calibration_sha256"]
                    != packet.diagnostic_calibration_sha256
                    or proof["gateway_attestation_sha256"]
                    != hashlib.sha256(signed_gateway_attestation).hexdigest()
                    or proof["response_code_details"] != packet.denial_response_code_details
                    or upstream_attempts != 0
                    or proof["app_log_absent"] is not True
                    or proof["app_logs_complete"] is not True
                    or not _SHA256.fullmatch(str(gateway["response_sha256"]))
                    or not _SHA256.fullmatch(str(proof["diagnostics_sha256"]))
                    or proof["arm_state_sha256"] != packet.expected_deny_state_sha256
                    or gateway_issued > sample.utc_ns + sample.uncertainty_ns
                    or proof_issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - proof_issued > MAX_RECEIPT_AGE_NS
                    or gateway_issued < auth_issued - sample.uncertainty_ns
                    or gateway_issued >= probe_expires
                    or probe_started - probe_uncertainty < marker_ready + marker_uncertainty
                    or ingress_started - ingress_uncertainty < marker_ready + marker_uncertainty
                    or ingress_started - ingress_uncertainty < probe_started + probe_uncertainty
                    or ingress_started + ingress_uncertainty
                    > response_observed - response_uncertainty
                    or response_observed + response_uncertainty > gateway_issued - probe_uncertainty
                    or probe_started > gateway_issued
                    or ingress_started > diagnostic_time
                    or probe_started + probe_uncertainty >= probe_expires
                    or ingress_started + ingress_uncertainty >= probe_expires
                    or response_observed + response_uncertainty >= probe_expires
                    or diagnostic_time < gateway_issued - sample.uncertainty_ns
                    or arm_time < gateway_issued - sample.uncertainty_ns
                    or diagnostic_time > proof_issued + sample.uncertainty_ns
                    or arm_time > proof_issued + sample.uncertainty_ns
                    or proof_issued - arm_time > MAX_RECEIPT_AGE_NS
                    or sample.utc_ns + sample.uncertainty_ns >= proof_expires
                    or sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                    or (phase == "post-restart" and not self._restart_verified)
                ):
                    raise AuthorizationError("origin denial proof is invalid or incomplete")
                transition = self._transition
            proof_record = canonical_json(
                {
                    "session_id": packet.session_id,
                    "phase": phase,
                    "gateway_attestation_sha256": hashlib.sha256(
                        signed_gateway_attestation
                    ).hexdigest(),
                    "verifier_proof_sha256": hashlib.sha256(signed_verifier_proof).hexdigest(),
                }
            )
            await self._ledger.create(
                self._record_name(packet.session_id, "probe-proof", phase),
                proof_record,
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.DENY_PROBES:
                    raise ClosedError("probe evidence completed after terminal closure")
                sample = self._sample()
                if (
                    sample.utc_ns + sample.uncertainty_ns >= proof_expires
                    or sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                    or sample.utc_ns - proof_issued > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("probe evidence completed after its deadline")
                self._verified_probes.add(phase)
                self._probe_proof_hashes[phase] = hashlib.sha256(signed_verifier_proof).hexdigest()
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def issue_challenge(self) -> str:
        try:
            async with self._lock:
                sample = self._sample()
                if self._packet is None or self._phase not in {
                    Phase.ARMED,
                    Phase.ACTIVE,
                    Phase.CASE_PENDING,
                }:
                    raise ClosedError("gateway is not awaiting a heartbeat")
                if sample.utc_ns + sample.uncertainty_ns >= self._packet.not_after_utc_ns:
                    raise ClosedError("signed absolute deadline has expired")
                if (
                    self._phase in {Phase.ACTIVE, Phase.CASE_PENDING}
                    and sample.boottime_ns >= self._lease_expires_boottime_ns
                ):
                    raise ClosedError("lease expired before heartbeat challenge")
                self._challenge = secrets.token_urlsafe(24)
                return self._challenge
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def renew(self, signed_heartbeat: bytes) -> int:
        try:
            payload = verify_object(
                signed_heartbeat,
                expected_kind="heartbeat",
                expected_role=KeyRole.SUPERVISOR,
                keyring=self._keyring,
                expected_key_id=(
                    self._packet.supervisor_key_id if self._packet is not None else None
                ),
            )
            heartbeat = require_exact_keys(
                payload,
                {
                    "session_id",
                    "challenge",
                    "checked_at_utc_ns",
                    "process_id",
                    "process_start_id",
                },
                label="heartbeat",
            )
            async with self._lock:
                sample = self._sample()
                packet = self._packet
                if packet is None or self._phase not in {
                    Phase.ARMED,
                    Phase.ACTIVE,
                    Phase.CASE_PENDING,
                }:
                    raise ClosedError("gateway is not accepting heartbeats")
                if heartbeat["session_id"] != packet.session_id:
                    raise AuthorizationError("heartbeat session does not match")
                if heartbeat["challenge"] != self._challenge or not self._challenge:
                    raise AuthorizationError("heartbeat challenge is stale or replayed")
                _integer(
                    heartbeat["process_id"],
                    "heartbeat process ID",
                    minimum=1,
                    maximum=MAX_PROCESS_ID,
                )
                process_start_id = heartbeat["process_start_id"]
                if not isinstance(process_start_id, str) or not _PROCESS_START_ID.fullmatch(
                    process_start_id
                ):
                    raise ProtocolError("heartbeat lacks exact child identity")
                checked_at = _integer(
                    heartbeat["checked_at_utc_ns"],
                    "heartbeat checked_at",
                    minimum=1,
                )
                if (
                    checked_at > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - checked_at > MAX_HEARTBEAT_AGE_NS
                    or (
                        self._phase in {Phase.ACTIVE, Phase.CASE_PENDING}
                        and sample.boottime_ns >= self._lease_expires_boottime_ns
                    )
                ):
                    raise ClosedError("heartbeat time is stale, future, or after expiry")
                expires_utc = min(
                    checked_at + packet.lease_ttl_ns - sample.uncertainty_ns,
                    packet.not_after_utc_ns - sample.uncertainty_ns,
                )
                remaining = expires_utc - sample.utc_ns - sample.uncertainty_ns
                if remaining <= 0:
                    raise ClosedError("heartbeat cannot establish a positive lease")
                self._lease_expires_boottime_ns = sample.boottime_ns + remaining
                self._challenge = None
                if self._phase is Phase.ARMED:
                    self._phase = Phase.ACTIVE
                return self._lease_expires_boottime_ns
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def prepare_dispatch(self, case_id: str, body: bytes) -> DispatchPermit:
        try:
            async with self._lock:
                sample = self._sample()
                self._check_live(sample)
                packet = self._packet
                if packet is None or self._next_case >= len(packet.cases):
                    raise ClosedError("all packet cases are already consumed")
                case = packet.cases[self._next_case]
                body_hash = hashlib.sha256(body).hexdigest()
                if (
                    case.case_id != case_id
                    or len(body) > packet.max_request_bytes
                    or body_hash != case.body_sha256
                    or self._pending is not None
                    or self._dispatched is not None
                ):
                    raise AuthorizationError("request does not match the next approved case")
                _validate_case_body(body, case)
                permit = DispatchPermit(
                    session_id=packet.session_id,
                    case_id=case.case_id,
                    body_sha256=body_hash,
                    record_sha256="",
                    token=secrets.token_urlsafe(24),
                    prepared_utc_ns=0,
                    prepared_uncertainty_ns=0,
                )
                self._pending = permit
                self._phase = Phase.CASE_PENDING
                self._transition += 1
                transition = self._transition
            record = canonical_json(
                {
                    "session_id": permit.session_id,
                    "case_id": permit.case_id,
                    "order": self._next_case,
                    "body_sha256": body_hash,
                    "allocation_id": packet.allocation_id,
                    "allocation_sha256": packet.allocation_sha256,
                }
            )
            budget_record = canonical_json(
                {
                    "allocation_id": packet.allocation_id,
                    "allocation_sha256": packet.allocation_sha256,
                    "session_id": packet.session_id,
                    "case_id": case.case_id,
                    "reserve_microusd": case.reserve_microusd,
                }
            )
            await self._budget_ledger.create(
                self._budget_record_name(
                    "program-slot",
                    packet.allocation_id,
                    case.case_id,
                ),
                budget_record,
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.CASE_PENDING:
                    raise ClosedError("budget slot completed after closure")
                self._check_live(self._sample())
            record_hash = await self._ledger.create(
                self._record_name(packet.session_id, "dispatch", case.case_id),
                record,
            )
            async with self._lock:
                sample = self._sample()
                if (
                    self._transition != transition
                    or self._phase is not Phase.CASE_PENDING
                    or self._pending != permit
                ):
                    raise ClosedError("dispatch ledger write completed after closure")
                self._check_live(sample)
                permit = DispatchPermit(
                    session_id=permit.session_id,
                    case_id=permit.case_id,
                    body_sha256=permit.body_sha256,
                    record_sha256=record_hash,
                    token=permit.token,
                    prepared_utc_ns=sample.utc_ns,
                    prepared_uncertainty_ns=sample.uncertainty_ns,
                )
                self._pending = permit
                return permit
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def authorize_and_initiate(
        self,
        permit: DispatchPermit,
        signed_receipt: bytes,
        initiate_nonblocking_write: Callable[[], bool],
    ) -> None:
        """Validate fresh verifier receipt and classify synchronous write initiation.

        The callback must initiate only the first bounded nonblocking upstream
        write; it must not await network I/O or perform retries.
        """
        try:
            receipt = verify_object(
                signed_receipt,
                expected_kind="pre-dispatch-receipt",
                expected_role=KeyRole.FINANCIAL_VERIFIER,
                keyring=self._keyring,
                expected_key_id=(
                    self._packet.financial_verifier_key_id if self._packet is not None else None
                ),
            )
            data = require_exact_keys(
                receipt,
                {
                    "session_id",
                    "case_id",
                    "dispatch_sha256",
                    "config_sha256",
                    "snapshot_sha256",
                    "prior_state_sha256",
                    "snapshot_observed_utc_ns",
                    "snapshot_uncertainty_ns",
                    "input_upper_bound_tokens",
                    "cost_ceiling_microusd",
                    "cost_proof_sha256",
                    "issued_utc_ns",
                    "expires_utc_ns",
                },
                label="pre-dispatch receipt",
            )
            async with self._lock:
                sample = self._sample()
                self._check_live(sample)
                if self._pending != permit or self._phase is not Phase.CASE_PENDING:
                    raise AuthorizationError("dispatch permit is stale")
                packet = self._packet
                if packet is None:
                    raise ClosedError("session is unavailable")
                issued = _integer(data["issued_utc_ns"], "receipt issued time", minimum=1)
                expires = _integer(data["expires_utc_ns"], "receipt expiry", minimum=1)
                observed = _integer(data["snapshot_observed_utc_ns"], "snapshot time", minimum=1)
                snapshot_uncertainty = _integer(
                    data["snapshot_uncertainty_ns"],
                    "snapshot uncertainty",
                    minimum=0,
                    maximum=MAX_CLOCK_UNCERTAINTY_NS,
                )
                case = packet.cases[self._next_case]
                input_bound = _integer(data["input_upper_bound_tokens"], "input bound", minimum=1)
                cost_ceiling = _integer(data["cost_ceiling_microusd"], "cost ceiling", minimum=1)
                if (
                    data["session_id"] != permit.session_id
                    or data["case_id"] != permit.case_id
                    or data["dispatch_sha256"] != permit.record_sha256
                    or data["config_sha256"] != packet.config_sha256
                    or not _SHA256.fullmatch(str(data["snapshot_sha256"]))
                    or data["prior_state_sha256"] != self._last_state_sha256
                    or not _SHA256.fullmatch(str(data["cost_proof_sha256"]))
                    or input_bound > case.max_input_tokens
                    or cost_ceiling > case.reserve_microusd
                    or observed - snapshot_uncertainty
                    < permit.prepared_utc_ns + permit.prepared_uncertainty_ns
                    or snapshot_uncertainty + sample.uncertainty_ns > MAX_CLOCK_UNCERTAINTY_NS
                    or observed > issued
                    or sample.utc_ns + sample.uncertainty_ns - (observed - snapshot_uncertainty)
                    > MAX_RECEIPT_AGE_NS
                    or issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                    or expires <= sample.utc_ns + sample.uncertainty_ns
                    or expires > packet.not_after_utc_ns
                ):
                    raise AuthorizationError("receipt is stale or not bound to this dispatch")
                if not initiate_nonblocking_write():
                    raise ClosedError("upstream write initiation did not complete")
                self._pending = None
                self._dispatched = permit
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def advance(self, signed_witness: bytes, signed_settlement: bytes) -> None:
        """Consume verifier-confirmed response/settlement evidence exactly once."""
        try:
            witness = verify_object(
                signed_witness,
                expected_kind="response-witness",
                expected_role=KeyRole.GATEWAY,
                keyring=self._keyring,
                expected_key_id=self._packet.gateway_key_id if self._packet is not None else None,
            )
            witnessed = require_exact_keys(
                witness,
                {
                    "session_id",
                    "case_id",
                    "dispatch_sha256",
                    "response_sha256",
                    "issued_utc_ns",
                    "status_code",
                    "completed",
                    "clean_eof",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                },
                label="gateway response witness",
            )
            settlement = verify_object(
                signed_settlement,
                expected_kind="settlement",
                expected_role=KeyRole.FINANCIAL_VERIFIER,
                keyring=self._keyring,
                expected_key_id=(
                    self._packet.financial_verifier_key_id if self._packet is not None else None
                ),
            )
            data = require_exact_keys(
                settlement,
                {
                    "session_id",
                    "case_id",
                    "dispatch_sha256",
                    "response_witness_sha256",
                    "post_snapshot_sha256",
                    "post_state_sha256",
                    "accounts_sha256",
                    "process_id",
                    "issued_utc_ns",
                },
                label="settlement",
            )
            async with self._lock:
                sample = self._sample()
                self._check_live(sample)
                packet = self._packet
                permit = self._dispatched
                if packet is None or permit is None:
                    raise ClosedError("no dispatched case is awaiting settlement")
                issued = _integer(data["issued_utc_ns"], "settlement issued time", minimum=1)
                witness_issued = _integer(
                    witnessed["issued_utc_ns"], "witness issued time", minimum=1
                )
                status_code = _integer(
                    witnessed["status_code"],
                    "status_code",
                    minimum=MIN_HTTP_STATUS,
                    maximum=MAX_HTTP_STATUS,
                )
                input_tokens = _integer(
                    witnessed["input_tokens"],
                    "input_tokens",
                    minimum=0,
                    maximum=1_000_000_000,
                )
                output_tokens = _integer(
                    witnessed["output_tokens"],
                    "output_tokens",
                    minimum=0,
                    maximum=1_000_000_000,
                )
                total_tokens = _integer(witnessed["total_tokens"], "total_tokens", minimum=0)
                process = _identifier(data["process_id"], "settled process")
                case = packet.cases[self._next_case]
                if (
                    data["session_id"] != packet.session_id
                    or data["case_id"] != case.case_id
                    or data["dispatch_sha256"] != permit.record_sha256
                    or witnessed["session_id"] != packet.session_id
                    or witnessed["case_id"] != case.case_id
                    or witnessed["dispatch_sha256"] != permit.record_sha256
                    or data["response_witness_sha256"] != hashlib.sha256(signed_witness).hexdigest()
                    or not _SHA256.fullmatch(str(witnessed["response_sha256"]))
                    or not _SHA256.fullmatch(str(data["post_snapshot_sha256"]))
                    or not _SHA256.fullmatch(str(data["post_state_sha256"]))
                    or not _SHA256.fullmatch(str(data["accounts_sha256"]))
                    or process != self._last_process
                    or total_tokens != input_tokens + output_tokens
                    or issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                    or witness_issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - witness_issued > MAX_RECEIPT_AGE_NS
                    or status_code != HTTP_OK
                    or witnessed["completed"] is not True
                    or witnessed["clean_eof"] is not True
                    or input_tokens > case.max_input_tokens
                    or output_tokens > case.max_output_tokens
                ):
                    raise AuthorizationError("settlement does not prove a successful case")
                self._phase = Phase.CLOSING
                self._transition += 1
                transition = self._transition
            record = canonical_json(
                {
                    "session_id": packet.session_id,
                    "case_id": case.case_id,
                    "dispatch_sha256": permit.record_sha256,
                    "settlement_sha256": hashlib.sha256(signed_settlement).hexdigest(),
                }
            )
            await self._ledger.create(
                self._record_name(packet.session_id, "advance", case.case_id),
                record,
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.CLOSING:
                    raise ClosedError("settlement completed after session closure")
                sample = self._sample()
                if (
                    sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                    or sample.boottime_ns >= self._lease_expires_boottime_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                    or sample.utc_ns - witness_issued > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("lease expired while settlement was being recorded")
                self._next_case += 1
                self._last_state_sha256 = str(data["post_state_sha256"])
                self._last_accounts_sha256 = str(data["accounts_sha256"])
                self._last_process = process
                self._dispatched = None
                self._phase = Phase.ACTIVE
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def close_for_deny(self) -> str:
        """Irreversibly close forwarding before attempting the close marker."""
        try:
            async with self._lock:
                sample = self._sample()
                packet = self._packet
                if (
                    packet is None
                    or self._phase is not Phase.ACTIVE
                    or self._next_case != len(packet.cases)
                    or self._pre_deny_health_sha256 is None
                ):
                    raise ClosedError("all four successful cases are required before close")
                if (
                    sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                    or sample.boottime_ns >= self._lease_expires_boottime_ns
                    or self._pre_deny_health_issued_utc_ns is None
                    or sample.utc_ns - self._pre_deny_health_issued_utc_ns > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("close requested after deadline or lease expiry")
                self._phase = Phase.CLOSING
                self._challenge = None
                self._transition += 1
                transition = self._transition
            close_hash = await self._ledger.create(
                self._record_name(packet.session_id, "close", packet.session_id),
                canonical_json(
                    {
                        "session_id": packet.session_id,
                        "packet_sha256": packet.raw_sha256,
                        "closed_utc_ns": self._sample().utc_ns,
                    }
                ),
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.CLOSING:
                    raise ClosedError("close marker completed after terminal closure")
                sample = self._sample()
                if (
                    sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                    or sample.boottime_ns >= self._lease_expires_boottime_ns
                    or self._pre_deny_health_issued_utc_ns is None
                    or sample.utc_ns - self._pre_deny_health_issued_utc_ns > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("close marker completed after lease expiry")
                self._phase = Phase.DENY_PROBES
                self._close_sha256 = close_hash
            return close_hash
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def record_pre_deny_health(self, signed_attestation: bytes) -> None:
        """Record a packet-bound, successful origin health check before closing."""
        try:
            data = require_exact_keys(
                verify_object(
                    signed_attestation,
                    expected_kind="pre-deny-health",
                    expected_role=KeyRole.GATEWAY,
                    keyring=self._keyring,
                    expected_key_id=self._packet.gateway_key_id if self._packet else None,
                ),
                {
                    "session_id",
                    "origin_host",
                    "status_code",
                    "tls_valid",
                    "request_id",
                    "challenge",
                    "issued_utc_ns",
                },
                label="pre-DENY health",
            )
            async with self._lock:
                sample = self._sample()
                self._check_live(sample)
                packet = self._packet
                if (
                    packet is None
                    or self._next_case != len(packet.cases)
                    or self._pre_deny_health_sha256
                ):
                    raise ClosedError("pre-DENY health is out of phase")
                issued = _integer(data["issued_utc_ns"], "health issue time", minimum=1)
                _identifier(data["request_id"], "health request ID")
                if (
                    data["session_id"] != packet.session_id
                    or data["origin_host"] != packet.origin_host
                    or data["status_code"] != HTTP_OK
                    or data["tls_valid"] is not True
                    or self._pre_deny_challenge is None
                    or data["challenge"] != self._pre_deny_challenge
                    or self._pre_deny_challenge_issued_utc_ns is None
                    or self._pre_deny_challenge_uncertainty_ns is None
                    or issued - sample.uncertainty_ns
                    < self._pre_deny_challenge_issued_utc_ns
                    + self._pre_deny_challenge_uncertainty_ns
                    or issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                ):
                    raise AuthorizationError("pre-DENY health attestation is invalid")
                transition = self._transition
            digest = await self._ledger.create(
                self._record_name(packet.session_id, "pre-deny-health", packet.session_id),
                canonical_json(
                    {"attestation_sha256": hashlib.sha256(signed_attestation).hexdigest()}
                ),
            )
            async with self._lock:
                sample = self._sample()
                self._check_live(sample)
                if self._transition != transition or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS:
                    raise ClosedError("health attestation completed after closure")
                self._pre_deny_health_sha256 = digest
                self._pre_deny_health_issued_utc_ns = issued
                self._pre_deny_challenge = None
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def issue_pre_deny_health_challenge(self) -> str:
        """Issue an unpredictable challenge only after the final settlement."""
        try:
            async with self._lock:
                sample = self._sample()
                self._check_live(sample)
                if (
                    self._packet is None
                    or self._next_case != len(self._packet.cases)
                    or self._pre_deny_health_sha256 is not None
                    or self._pre_deny_challenge is not None
                ):
                    raise ClosedError("pre-DENY health challenge is out of phase")
                self._pre_deny_challenge = secrets.token_urlsafe(24)
                self._pre_deny_challenge_issued_utc_ns = sample.utc_ns
                self._pre_deny_challenge_uncertainty_ns = sample.uncertainty_ns
                return self._pre_deny_challenge
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def authorize_deny(self, signed_authorization: bytes) -> str:
        """Consume the independent operator's one-use final-DENY authorization."""
        try:
            authorization = verify_object(
                signed_authorization,
                expected_kind="deny-authorization",
                expected_role=KeyRole.OPERATOR,
                keyring=self._keyring,
                expected_key_id=self._packet.operator_key_id if self._packet is not None else None,
            )
            data = require_exact_keys(
                authorization,
                {
                    "session_id",
                    "close_sha256",
                    "deny_config_sha256",
                    "issued_utc_ns",
                },
                label="deny authorization",
            )
            async with self._lock:
                sample = self._sample()
                packet = self._packet
                if (
                    packet is None
                    or self._phase is not Phase.DENY_PROBES
                    or self._deny_authorized
                    or self._deny_authorizing
                ):
                    raise ClosedError("DENY authorization is out of phase or consumed")
                if sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns:
                    raise ClosedError("DENY authorization was requested after packet expiry")
                issued = _integer(data["issued_utc_ns"], "DENY issue time", minimum=1)
                if (
                    data["session_id"] != packet.session_id
                    or data["close_sha256"] != self._close_sha256
                    or data["deny_config_sha256"] != packet.expected_deny_state_sha256
                    or issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                ):
                    raise AuthorizationError("DENY authorization is stale or mismatched")
                self._deny_authorizing = True
                self._transition += 1
                transition = self._transition
            marker = await self._ledger.create(
                self._record_name(packet.session_id, "deny", packet.session_id),
                canonical_json(
                    {
                        "session_id": packet.session_id,
                        "authorization_sha256": hashlib.sha256(signed_authorization).hexdigest(),
                    }
                ),
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.DENY_PROBES:
                    raise ClosedError("DENY marker completed after terminal closure")
                sample = self._sample()
                if (
                    sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("DENY marker completed after authorization expiry")
                self._deny_authorizing = False
                self._deny_authorized = True
            return marker
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def consume_probe(self, phase: str, signed_authorization: bytes) -> str:
        """Consume one verifier-authorized diagnostic probe; never reopens proxying."""
        try:
            authorization = verify_object(
                signed_authorization,
                expected_kind="probe-authorization",
                expected_role=KeyRole.FINANCIAL_VERIFIER,
                keyring=self._keyring,
                expected_key_id=(
                    self._packet.financial_verifier_key_id if self._packet is not None else None
                ),
            )
            data = require_exact_keys(
                authorization,
                {
                    "session_id",
                    "phase",
                    "request_id",
                    "issued_utc_ns",
                    "expires_utc_ns",
                    "proof_expires_utc_ns",
                },
                label="probe authorization",
            )
            async with self._lock:
                sample = self._sample()
                packet = self._packet
                if packet is None or self._phase is not Phase.DENY_PROBES:
                    raise ClosedError("diagnostic phase is not active")
                if not self._deny_authorized:
                    raise AuthorizationError("final DENY has not been authorized")
                if phase not in {"pre-restart", "post-restart"} or phase in self._probes:
                    raise AuthorizationError("probe phase is invalid or already consumed")
                if phase == "pre-restart" and self._probes:
                    raise AuthorizationError("pre-restart probe must be the first probe")
                if phase == "post-restart" and (
                    not self._restart_verified or "pre-restart" not in self._verified_probes
                ):
                    raise AuthorizationError("post-restart probe requires verified restart")
                issued = _integer(data["issued_utc_ns"], "probe issue time", minimum=1)
                expires = _integer(data["expires_utc_ns"], "probe expiry", minimum=1)
                proof_expires = _integer(data["proof_expires_utc_ns"], "proof expiry", minimum=1)
                request_id = _identifier(data["request_id"], "probe request ID")
                if (
                    data["session_id"] != packet.session_id
                    or data["phase"] != phase
                    or issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                    or expires <= sample.utc_ns + sample.uncertainty_ns
                    or proof_expires < expires
                    or proof_expires > packet.not_after_utc_ns
                    or any(context[2] == request_id for context in self._probe_context.values())
                ):
                    raise AuthorizationError("probe authorization is stale or out of scope")
                self._transition += 1
                transition = self._transition
            record_hash = await self._ledger.create(
                self._record_name(packet.session_id, "probe", phase),
                canonical_json(
                    {
                        "session_id": packet.session_id,
                        "phase": phase,
                        "authorization_sha256": hashlib.sha256(signed_authorization).hexdigest(),
                        "nonce": secrets.token_urlsafe(24),
                    }
                ),
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.DENY_PROBES:
                    raise ClosedError("probe marker completed after session closure")
                sample = self._sample()
                if (
                    sample.utc_ns + sample.uncertainty_ns >= expires
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("probe marker completed after operation expiry")
                self._probes.add(phase)
                self._probe_context[phase] = (
                    record_hash,
                    hashlib.sha256(signed_authorization).hexdigest(),
                    request_id,
                    issued,
                    expires,
                    proof_expires,
                    sample.utc_ns,
                    sample.uncertainty_ns,
                )
            return record_hash
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def authorize_restart(self, signed_authorization: bytes) -> str:
        """Durably consume operator restart authorization before mutation."""
        try:
            data = require_exact_keys(
                verify_object(
                    signed_authorization,
                    expected_kind="restart-authorization",
                    expected_role=KeyRole.OPERATOR,
                    keyring=self._keyring,
                    expected_key_id=self._packet.operator_key_id if self._packet else None,
                ),
                {
                    "session_id",
                    "target_config_sha256",
                    "restart_target_sha256",
                    "pre_probe_proof_sha256",
                    "process_before",
                    "accounts_sha256",
                    "issued_utc_ns",
                    "expires_utc_ns",
                },
                label="restart authorization",
            )
            async with self._lock:
                sample = self._sample()
                packet = self._packet
                if (
                    packet is None
                    or self._phase is not Phase.DENY_PROBES
                    or "pre-restart" not in self._verified_probes
                    or self._restart_marker_sha256
                ):
                    raise ClosedError("restart authorization is out of phase")
                issued = _integer(data["issued_utc_ns"], "restart issue time", minimum=1)
                expires = _integer(data["expires_utc_ns"], "restart expiry", minimum=1)
                if (
                    data["session_id"] != packet.session_id
                    or data["target_config_sha256"] != packet.config_sha256
                    or data["restart_target_sha256"] != packet.restart_target_sha256
                    or data["pre_probe_proof_sha256"] != self._probe_proof_hashes.get("pre-restart")
                    or data["process_before"] != self._last_process
                    or data["accounts_sha256"] != self._last_accounts_sha256
                    or issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                    or expires <= sample.utc_ns + sample.uncertainty_ns
                    or expires > packet.not_after_utc_ns
                ):
                    raise AuthorizationError("restart authorization is stale or mismatched")
                self._transition += 1
                transition = self._transition
            marker = await self._ledger.create(
                self._record_name(packet.session_id, "restart", packet.session_id),
                canonical_json(
                    {
                        "authorization_sha256": hashlib.sha256(signed_authorization).hexdigest(),
                        "nonce": secrets.token_urlsafe(24),
                    }
                ),
            )
            async with self._lock:
                sample = self._sample()
                if (
                    self._transition != transition
                    or self._phase is not Phase.DENY_PROBES
                    or sample.utc_ns + sample.uncertainty_ns >= expires
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("restart marker completed after authorization expiry")
                self._restart_marker_sha256 = marker
                self._restart_marker_ready_utc_ns = sample.utc_ns
                self._restart_authorization_expires_utc_ns = expires
            return marker
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def initiate_restart(
        self, marker_sha256: str, initiate_nonblocking_mutation: Callable[[str], bool]
    ) -> str:
        """Gate the trusted operator's one-shot mutation initiation before expiry."""
        try:
            async with self._lock:
                sample = self._sample()
                if (
                    self._packet is None
                    or self._phase is not Phase.DENY_PROBES
                    or marker_sha256 != self._restart_marker_sha256
                    or self._restart_initiated
                    or self._restart_authorization_expires_utc_ns is None
                    or sample.utc_ns + sample.uncertainty_ns
                    >= self._restart_authorization_expires_utc_ns
                ):
                    raise ClosedError("restart initiation is expired or not authorized")
                # The caller supplies a bounded nonblocking initiation, not an awaited mutation.
                nonce = secrets.token_urlsafe(24)
                self._restart_initiated = True
                self._restart_initiated_at_utc_ns = sample.utc_ns
                self._restart_initiated_uncertainty_ns = sample.uncertainty_ns
                self._restart_initiation_nonce = nonce
                if not initiate_nonblocking_mutation(nonce):
                    raise ClosedError("restart mutation initiation is ambiguous")
                return nonce
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def record_restart(self, signed_attestation: bytes, signed_start_proof: bytes) -> None:
        """Record one independently observed restart between the two probes."""
        try:
            attestation = verify_object(
                signed_attestation,
                expected_kind="restart-attestation",
                expected_role=KeyRole.OPERATOR,
                keyring=self._keyring,
                expected_key_id=self._packet.operator_key_id if self._packet is not None else None,
            )
            data = require_exact_keys(
                attestation,
                {
                    "session_id",
                    "process_before",
                    "process_after",
                    "restart_marker_sha256",
                    "pre_probe_proof_sha256",
                    "target_config_sha256",
                    "restart_target_sha256",
                    "start_proof_sha256",
                    "ready",
                    "sole_worker",
                    "accounts_sha256",
                    "issued_utc_ns",
                },
                label="restart attestation",
            )
            start = require_exact_keys(
                verify_object(
                    signed_start_proof,
                    expected_kind="restart-start-proof",
                    expected_role=KeyRole.FINANCIAL_VERIFIER,
                    keyring=self._keyring,
                    expected_key_id=(
                        self._packet.financial_verifier_key_id if self._packet else None
                    ),
                ),
                {
                    "session_id",
                    "restart_marker_sha256",
                    "restart_target_sha256",
                    "initiation_nonce",
                    "operation_started_utc_ns",
                    "operation_uncertainty_ns",
                    "evidence_sha256",
                    "issued_utc_ns",
                },
                label="restart start proof",
            )
            async with self._lock:
                sample = self._sample()
                packet = self._packet
                if (
                    packet is None
                    or self._phase is not Phase.DENY_PROBES
                    or "pre-restart" not in self._verified_probes
                    or self._restart_marker_sha256 is None
                    or not self._restart_initiated
                    or "post-restart" in self._probes
                    or self._restart_verified
                ):
                    raise ClosedError("restart attestation is out of phase")
                issued = _integer(data["issued_utc_ns"], "restart issue time", minimum=1)
                started = _integer(
                    start["operation_started_utc_ns"], "restart start time", minimum=1
                )
                start_uncertainty = _integer(
                    start["operation_uncertainty_ns"],
                    "restart start uncertainty",
                    minimum=0,
                    maximum=MAX_CLOCK_UNCERTAINTY_NS,
                )
                start_issued = _integer(start["issued_utc_ns"], "start proof time", minimum=1)
                if (
                    data["session_id"] != packet.session_id
                    or not isinstance(data["process_before"], str)
                    or not _IDENTIFIER.fullmatch(data["process_before"])
                    or not isinstance(data["process_after"], str)
                    or not _IDENTIFIER.fullmatch(data["process_after"])
                    or data["process_before"] == data["process_after"]
                    or data["process_before"] != self._last_process
                    or data["restart_marker_sha256"] != self._restart_marker_sha256
                    or data["pre_probe_proof_sha256"] != self._probe_proof_hashes.get("pre-restart")
                    or data["target_config_sha256"] != packet.config_sha256
                    or data["restart_target_sha256"] != packet.restart_target_sha256
                    or data["start_proof_sha256"] != hashlib.sha256(signed_start_proof).hexdigest()
                    or start["session_id"] != packet.session_id
                    or start["restart_marker_sha256"] != self._restart_marker_sha256
                    or start["restart_target_sha256"] != packet.restart_target_sha256
                    or start["initiation_nonce"] != self._restart_initiation_nonce
                    or not _SHA256.fullmatch(str(start["evidence_sha256"]))
                    or self._restart_marker_ready_utc_ns is None
                    or started < self._restart_marker_ready_utc_ns - sample.uncertainty_ns
                    or self._restart_initiated_at_utc_ns is None
                    or self._restart_initiated_uncertainty_ns is None
                    or started - start_uncertainty
                    < self._restart_initiated_at_utc_ns + self._restart_initiated_uncertainty_ns
                    or self._restart_authorization_expires_utc_ns is None
                    or started + start_uncertainty >= self._restart_authorization_expires_utc_ns
                    or start_issued < started - sample.uncertainty_ns
                    or start_issued > sample.utc_ns + sample.uncertainty_ns
                    or issued < started - sample.uncertainty_ns
                    or data["ready"] is not True
                    or data["sole_worker"] is not True
                    or data["accounts_sha256"] != self._last_accounts_sha256
                    or issued > sample.utc_ns + sample.uncertainty_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                    or sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                ):
                    raise AuthorizationError("restart attestation is invalid or stale")
                self._transition += 1
                transition = self._transition
            await self._ledger.create(
                self._record_name(packet.session_id, "restart-result", packet.session_id),
                canonical_json(
                    {
                        "session_id": packet.session_id,
                        "attestation_sha256": hashlib.sha256(signed_attestation).hexdigest(),
                    }
                ),
            )
            async with self._lock:
                if self._transition != transition or self._phase is not Phase.DENY_PROBES:
                    raise ClosedError("restart marker completed after session closure")
                sample = self._sample()
                if (
                    sample.utc_ns + sample.uncertainty_ns >= packet.not_after_utc_ns
                    or sample.utc_ns - issued > MAX_RECEIPT_AGE_NS
                ):
                    raise ClosedError("restart evidence completed after expiry")
                self._restart_verified = True
        except (Exception, asyncio.CancelledError):
            self._mark_terminal()
            raise

    async def fail_closed(self) -> None:
        """Public shutdown hook; no caller can reopen this process session."""
        await self._terminal()

    @staticmethod
    def _record_name(session_id: str, kind: str, key: str) -> str:
        session_digest = hashlib.sha256(session_id.encode("ascii")).hexdigest()
        key_digest = hashlib.sha256(key.encode("ascii")).hexdigest()
        return f"{kind}/{session_digest}/{key_digest}"

    @staticmethod
    def _budget_record_name(kind: str, allocation_id: str, slot_id: str | None = None) -> str:
        allocation_digest = hashlib.sha256(allocation_id.encode("ascii")).hexdigest()
        if slot_id is None:
            return f"{kind}/{allocation_digest}"
        slot_digest = hashlib.sha256(slot_id.encode("ascii")).hexdigest()
        return f"{kind}/{allocation_digest}/{slot_digest}"
