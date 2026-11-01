"""Insert-only ledger interface and test double.

The Azure adapter accepts an already-configured primary container client and
requires an independently verified locked-WORM attestation. Azure behavior is
not established by the local adapter tests.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlsplit

from .clock import MAX_CLOCK_UNCERTAINTY_NS, Clock
from .errors import AuthorizationError, LedgerError
from .schema import require_exact_keys
from .signing import KeyRole, VerificationKey, verify_object

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

MIN_SESSION_RETENTION_DAYS = 8
NANOSECONDS_PER_DAY = 86_400_000_000_000
SHA256_HEX_LENGTH = 64
MAX_ATTESTATION_AGE_NS = 60 * 1_000_000_000
MAX_ATTESTATION_LIFETIME_NS = 30 * 60 * 1_000_000_000
MAX_LEDGER_RECORD_BYTES = 16_384
_CONTAINER_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
_CLIENT_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_LEDGER_NAME = re.compile(r"^[a-z][a-z0-9-]{0,31}/[0-9a-f]{64}(?:/[0-9a-f]{64})?$")


class LedgerKind(StrEnum):
    SESSION = "session"
    BUDGET = "budget"
    REGISTRY = "registry"


class CreateOnlyLedger(Protocol):
    kind: LedgerKind
    namespace: str
    program_scope_sha256: str | None
    financial_retain_until_utc_ns: int | None

    async def create(self, name: str, payload: bytes) -> str: ...


class BlobClient(Protocol):
    def upload_blob(
        self,
        data: bytes,
        *,
        overwrite: bool,
        if_none_match: str,
        max_concurrency: int,
    ) -> dict[str, object]: ...


class BlobContainerClient(Protocol):
    url: str

    def get_blob_client(self, *, blob: str) -> BlobClient: ...


@dataclass(frozen=True, slots=True)
class WormAttestationBinding:
    operator_key_id: str
    account_url: str
    container_name: str
    managed_identity_client_id: str
    kind: LedgerKind
    program_scope_sha256: str | None = None
    financial_retain_until_utc_ns: int | None = None


@dataclass(frozen=True, slots=True)
class WormAttestation:
    account_url: str
    container_name: str
    managed_identity_client_id: str
    policy_evidence_sha256: str
    expires_utc_ns: int

    @classmethod
    def verify(
        cls,
        signed_attestation: bytes,
        *,
        keyring: dict[str, VerificationKey],
        binding: WormAttestationBinding,
        now_utc_ns: int,
        uncertainty_ns: int,
    ) -> WormAttestation:
        claims = verify_object(
            signed_attestation,
            expected_kind="worm-attestation",
            expected_role=KeyRole.OPERATOR,
            keyring=keyring,
            expected_key_id=binding.operator_key_id,
        )
        data = require_exact_keys(
            claims,
            {
                "account_url",
                "container_name",
                "managed_identity_client_id",
                "kind",
                "program_scope_sha256",
                "financial_retain_until_utc_ns",
                "legal_hold",
                "legal_hold_clear_denied",
                "policy_locked",
                "retention_days",
                "overwrite_denied",
                "delete_denied",
                "primary_endpoint_url",
                "automatic_failover",
                "retry_total",
                "retry_connect",
                "retry_read",
                "retry_status",
                "retry_to_secondary",
                "policy_evidence_sha256",
                "issued_utc_ns",
                "expires_utc_ns",
            },
            label="WORM attestation",
        )
        if not 0 <= uncertainty_ns <= MAX_CLOCK_UNCERTAINTY_NS:
            raise LedgerError("trusted clock uncertainty is invalid for WORM attestation")
        account_url = _https_account_url(binding.account_url)
        container_name = binding.container_name
        managed_identity_client_id = binding.managed_identity_client_id
        issued = _integer(data["issued_utc_ns"], "attestation issue time")
        expires = _integer(data["expires_utc_ns"], "attestation expiry")
        retention = _integer(data["retention_days"], "retention days")
        retries = (
            _integer(data["retry_total"], "total retries"),
            _integer(data["retry_connect"], "connection retries"),
            _integer(data["retry_read"], "read retries"),
            _integer(data["retry_status"], "status retries"),
        )
        evidence = data["policy_evidence_sha256"]
        if binding.kind in {LedgerKind.BUDGET, LedgerKind.REGISTRY}:
            scope = binding.program_scope_sha256
            until = binding.financial_retain_until_utc_ns
            if (
                not isinstance(scope, str)
                or not re.fullmatch(r"[0-9a-f]{64}", scope)
                or isinstance(until, bool)
                or not isinstance(until, int)
                or until <= now_utc_ns + uncertainty_ns
                or data["legal_hold"] is not True
                or data["legal_hold_clear_denied"] is not True
                or now_utc_ns - uncertainty_ns + retention * NANOSECONDS_PER_DAY < until
            ):
                raise AuthorizationError("budget retention or legal hold is insufficient")
        elif binding.kind is LedgerKind.SESSION:
            if (
                binding.program_scope_sha256 is not None
                or binding.financial_retain_until_utc_ns is not None
            ):
                raise LedgerError("session ledger cannot bind a financial scope")
        else:
            raise LedgerError("unknown ledger kind")
        if (
            data["account_url"] != account_url
            or data["container_name"] != container_name
            or data["managed_identity_client_id"] != managed_identity_client_id
            or data["kind"] != binding.kind.value
            or data["program_scope_sha256"] != binding.program_scope_sha256
            or data["financial_retain_until_utc_ns"] != binding.financial_retain_until_utc_ns
            or not isinstance(data["legal_hold"], bool)
            or not isinstance(data["legal_hold_clear_denied"], bool)
            or data["primary_endpoint_url"] != account_url
            or data["policy_locked"] is not True
            or retention < MIN_SESSION_RETENTION_DAYS
            or data["overwrite_denied"] is not True
            or data["delete_denied"] is not True
            or data["automatic_failover"] is not False
            or retries != (0, 0, 0, 0)
            or data["retry_to_secondary"] is not False
            or not isinstance(evidence, str)
            or len(evidence) != SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in evidence)
            or issued > now_utc_ns + uncertainty_ns
            or now_utc_ns - issued > MAX_ATTESTATION_AGE_NS
            or expires <= issued
            or expires <= now_utc_ns + uncertainty_ns
            or expires - issued > MAX_ATTESTATION_LIFETIME_NS
        ):
            raise AuthorizationError("signed locked-WORM attestation is invalid or stale")
        if not _CONTAINER_NAME.fullmatch(container_name):
            raise LedgerError("ledger container name is invalid")
        if not _CLIENT_ID.fullmatch(managed_identity_client_id):
            raise LedgerError("managed identity client ID is invalid")
        return cls(
            account_url=account_url,
            container_name=container_name,
            managed_identity_client_id=managed_identity_client_id,
            policy_evidence_sha256=evidence,
            expires_utc_ns=expires,
        )


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LedgerError(f"{label} must be a nonnegative integer")
    return value


def _https_account_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise LedgerError("ledger account URL is malformed") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.isascii()
        or parsed.hostname != parsed.hostname.lower()
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or port is not None
        or parsed.netloc != parsed.hostname
    ):
        raise LedgerError("ledger account URL must be a plain HTTPS account endpoint")
    return f"https://{parsed.netloc}"


class MemoryCreateOnlyLedger:
    """Concurrency-safe, process-local ledger for tests only."""

    def __init__(
        self,
        *,
        kind: LedgerKind = LedgerKind.SESSION,
        namespace: str = "test-session",
        program_scope_sha256: str | None = None,
        financial_retain_until_utc_ns: int | None = None,
    ) -> None:
        self.kind = kind
        self.namespace = namespace
        self.program_scope_sha256 = program_scope_sha256
        self.financial_retain_until_utc_ns = financial_retain_until_utc_ns
        self._records: dict[str, bytes] = {}
        self._lock = asyncio.Lock()
        self.before_create: Callable[[str, bytes], Awaitable[None] | None] | None = None

    async def create(self, name: str, payload: bytes) -> str:
        if not name or not payload or len(payload) > MAX_LEDGER_RECORD_BYTES:
            raise LedgerError("ledger record name and payload are required")
        callback = self.before_create
        if callback is not None:
            result = callback(name, payload)
            if inspect.isawaitable(result):
                await result
        async with self._lock:
            if name in self._records:
                raise LedgerError("ledger record already exists")
            self._records[name] = bytes(payload)
        return hashlib.sha256(payload).hexdigest()

    async def read_for_forensics(self, name: str) -> bytes | None:
        async with self._lock:
            value = self._records.get(name)
            return None if value is None else bytes(value)

    async def record_names(self) -> tuple[str, ...]:
        async with self._lock:
            return tuple(sorted(self._records))


class AzureBlobCreateOnlyLedger:
    """Single-attempt conditional Blob writes through a preconfigured client.

    The caller must provide a primary-endpoint managed-identity client whose
    SDK retry policy is disabled, plus operator-attested WORM state. No read is
    used to convert a failed or ambiguous write into permission.
    """

    def __init__(
        self,
        container_client: BlobContainerClient,
        *,
        signed_attestation: bytes,
        keyring: dict[str, VerificationKey],
        binding: WormAttestationBinding,
        clock: Clock,
    ) -> None:
        sample = clock.sample()
        if not sample.trusted or not 0 <= sample.uncertainty_ns <= MAX_CLOCK_UNCERTAINTY_NS:
            raise LedgerError("trusted clock is required to verify WORM policy")
        attestation = WormAttestation.verify(
            signed_attestation,
            keyring=keyring,
            binding=binding,
            now_utc_ns=sample.utc_ns,
            uncertainty_ns=sample.uncertainty_ns,
        )
        expected_container_url = f"{attestation.account_url}/{attestation.container_name}"
        if getattr(container_client, "url", None) != expected_container_url:
            raise LedgerError("Blob client endpoint does not match the attested container")
        self._validate_managed_identity(
            container_client,
            expected_client_id=attestation.managed_identity_client_id,
        )
        self._validate_single_attempt_transport(container_client)
        self._container_client = container_client
        self._clock = clock
        self._attestation = attestation
        self.kind = binding.kind
        self.namespace = expected_container_url
        self.program_scope_sha256 = binding.program_scope_sha256
        self.financial_retain_until_utc_ns = binding.financial_retain_until_utc_ns

    @staticmethod
    def _validate_managed_identity(
        container_client: BlobContainerClient,
        *,
        expected_client_id: str,
    ) -> None:
        try:
            identity_module = importlib.import_module("azure.identity")
        except ImportError as exc:
            raise LedgerError("Azure Identity SDK is required for the Blob ledger") from exc
        credential_type = getattr(identity_module, "ManagedIdentityCredential", None)
        credential = getattr(container_client, "credential", None)
        implementation = getattr(credential, "_credential", None)
        settings = getattr(implementation, "_settings", None)
        if (
            not isinstance(credential_type, type)
            or not isinstance(credential, credential_type)
            or not isinstance(settings, dict)
            or settings.get("client_id") != expected_client_id
        ):
            raise LedgerError("Blob client is not bound to the attested managed identity")

    @staticmethod
    def _validate_single_attempt_transport(container_client: BlobContainerClient) -> None:
        config = getattr(container_client, "_config", None)
        retry_policy = getattr(config, "retry_policy", None)
        retry_counts = tuple(
            getattr(retry_policy, attribute, None)
            for attribute in ("total_retries", "connect_retries", "read_retries", "status_retries")
        )
        transport = getattr(config, "transport", None)
        if (
            retry_counts != (0, 0, 0, 0)
            or getattr(retry_policy, "retry_to_secondary", None) is not False
            or getattr(transport, "_use_env_settings", None) is not False
        ):
            raise LedgerError(
                "Blob client retries, secondary reads, or proxy environment are enabled"
            )

    async def create(self, name: str, payload: bytes) -> str:
        self._check_attestation()
        if (
            not _LEDGER_NAME.fullmatch(name)
            or not payload
            or len(payload) > MAX_LEDGER_RECORD_BYTES
        ):
            raise LedgerError("invalid ledger record")
        try:
            blob = self._container_client.get_blob_client(blob=name)
            response = await asyncio.to_thread(
                blob.upload_blob,
                payload,
                overwrite=False,
                if_none_match="*",
                max_concurrency=1,
            )
        except Exception as exc:
            # Any exception, including a conflict or lost acknowledgement, is
            # terminal. The caller must not retry or infer success from a read.
            raise LedgerError("conditional ledger create failed or is ambiguous") from exc
        self._check_attestation()
        if (
            not isinstance(response, dict)
            or not isinstance(response.get("etag"), str)
            or not response["etag"]
        ):
            raise LedgerError("ledger create did not return an explicit success response")
        return hashlib.sha256(payload).hexdigest()

    def _check_attestation(self) -> None:
        sample = self._clock.sample()
        if (
            not sample.trusted
            or not 0 <= sample.uncertainty_ns <= MAX_CLOCK_UNCERTAINTY_NS
            or sample.utc_ns + sample.uncertainty_ns >= self._attestation.expires_utc_ns
        ):
            raise LedgerError("WORM attestation or trusted clock expired during ledger operation")
