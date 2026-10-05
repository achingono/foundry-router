"""Concrete Azure Table Storage entity client (Phase 11).

Built on ``azure.data.tables.aio`` with token-credential authentication only.
Shared-key, SAS and connection-string code paths are intentionally absent;
:mod:`foundry_router.state.table` stays importable without the Azure SDK
(the SDK is imported lazily here, only when a Table client is constructed).

Credential selection (decision D2): ``ManagedIdentityCredential`` when running
in Azure Container Apps, ``DefaultAzureCredential`` only for local developer
runs against a real account.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Mapping

    from foundry_router.state.table import _TransactionEntity

_logger = structlog.get_logger(__name__)

_BALANCE_ROW_KEY = "balance"
_MAX_UNICODE_SCALAR = 0x10FFFF


def _is_container_apps() -> bool:
    """Detect the Container Apps runtime for credential selection (D2)."""
    return bool(os.environ.get("CONTAINER_APP_NAME"))


def select_credential() -> Any:
    """Return the token credential for Table access (D2).

    Managed identity in Container Apps; developer credential chain locally.
    No shared-key, SAS or connection-string path exists.
    """
    client_id = os.environ.get("FOUNDRY_AZURE_CLIENT_ID")
    if _is_container_apps() or client_id:
        from azure.identity.aio import ManagedIdentityCredential

        return (
            ManagedIdentityCredential(client_id=client_id)
            if client_id
            else ManagedIdentityCredential()
        )
    from azure.identity.aio import DefaultAzureCredential

    return DefaultAzureCredential()


def normalise_entity(entity: Mapping[str, Any]) -> dict[str, Any]:
    """Bridge SDK ETag metadata into the adapter's ``odata.etag`` key.

    The async SDK surfaces the ETag as ``entity.metadata['etag']`` while the
    adapter reads ``"odata.etag"``. Every returned entity is normalised so the
    adapter receives the ETag; entities without one keep no ETag key.
    """
    # Extract metadata as attribute (not dict key) since TableEntity.metadata
    # is a property, not a dict key. dict(TableEntity) drops the metadata.
    metadata = getattr(entity, "metadata", None)
    if metadata is None and isinstance(entity, dict):
        metadata = entity.get("metadata")
    data = dict(entity)
    etag: Any = None
    if isinstance(metadata, dict):
        etag = metadata.get("etag")
    if etag is None and "odata.etag" not in data:
        etag = getattr(entity, "etag", None)
    if etag is not None:
        data["odata.etag"] = etag
    return data


def prefix_upper_bound(prefix: str) -> str:
    """Return the exclusive RowKey upper bound for a prefix scan."""
    if not prefix:
        raise ValueError("prefix must not be empty")
    last = ord(prefix[-1])
    if last >= _MAX_UNICODE_SCALAR:
        raise ValueError("prefix cannot be incremented")
    return prefix[:-1] + chr(last + 1)


def _map_operation(op: _TransactionEntity) -> Any:
    """Map one adapter operation to an SDK transaction tuple."""
    from azure.core import MatchConditions
    from azure.data.tables import UpdateMode

    if op.operation == "Create":
        return ("create", dict(op.entity or {}))
    if op.operation in ("Update", "UpdateMerge"):
        if op.row_key == _BALANCE_ROW_KEY and op.etag is None:
            raise TableEntityMissingEtagError("balance write without ETag is refused (fail closed)")
        mode = UpdateMode.REPLACE if op.operation == "Update" else UpdateMode.MERGE
        kwargs: dict[str, Any] = {"mode": mode}
        if op.etag is not None:
            kwargs["match_condition"] = MatchConditions.IfNotModified
            kwargs["etag"] = op.etag
        return ("update", dict(op.entity or {}), kwargs)
    if op.operation == "Delete":
        key = {"PartitionKey": op.partition_key, "RowKey": op.row_key}
        if op.etag is not None:
            return (
                "delete",
                key,
                {"match_condition": MatchConditions.IfNotModified, "etag": op.etag},
            )
        if op.row_key == _BALANCE_ROW_KEY:
            raise TableEntityMissingEtagError(
                "balance delete without ETag is refused (fail closed)"
            )
        return ("delete", key)
    raise ValueError(f"unsupported transaction operation {op.operation!r}")


class AzureTableEntityClient:
    """Async :class:`TableEntityClient` on ``azure.data.tables.aio.TableClient``."""

    def __init__(
        self,
        *,
        endpoint: str,
        table_name: str,
        credential: Any | None = None,
        request_timeout_seconds: float = 5.0,
        allow_http_for_testing: bool = False,
    ) -> None:
        if not endpoint.startswith("https://") and not (
            allow_http_for_testing and endpoint.startswith("http://")
        ):
            raise ValueError("table endpoint must use https (or http for local testing)")
        self._endpoint = endpoint
        self._table_name = table_name
        self._credential = credential or select_credential()
        self._timeout = request_timeout_seconds
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from azure.data.tables.aio import TableClient

            self._client = TableClient(
                self._endpoint,
                table_name=self._table_name,
                credential=self._credential,
                connection_timeout=self._timeout,
                read_timeout=self._timeout,
                retry_total=1,
                retry_backoff_max=0.5,
            )
        return self._client

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.close()
        close_credential = getattr(self._credential, "close", None)
        if close_credential is not None:
            result = close_credential()
            if hasattr(result, "__await__"):
                await result

    async def get_entity(self, partition_key: str, row_key: str) -> Mapping[str, Any] | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            entity = await self._get_client().get_entity(
                partition_key=partition_key, row_key=row_key
            )
        except ResourceNotFoundError:
            return None
        except Exception as exc:
            _logger.warning(
                "table_get_failed",
                table=self._table_name,
                error_type=type(exc).__name__,
            )
            raise
        else:
            return normalise_entity(entity)

    async def upsert_entity(self, entity: Mapping[str, Any]) -> None:
        from azure.data.tables import UpdateMode

        try:
            await self._get_client().upsert_entity(dict(entity), mode=UpdateMode.REPLACE)
        except Exception as exc:
            _logger.warning(
                "table_upsert_failed",
                table=self._table_name,
                error_type=type(exc).__name__,
            )
            raise

    async def try_create_entity(self, entity: Mapping[str, Any]) -> bool:
        """Create only if absent; False when the row already exists."""
        from azure.core.exceptions import HttpResponseError, ResourceExistsError

        try:
            await self._get_client().create_entity(dict(entity))
        except HttpResponseError as exc:
            if _error_code(exc) == "EntityAlreadyExists":
                return False
            if isinstance(exc, ResourceExistsError):
                # Some SDK/emulator versions omit the specific code on a create race.
                # Confirm the requested row exists; an arbitrary 409 is not success.
                existing = await self.get_entity(str(entity["PartitionKey"]), str(entity["RowKey"]))
                if existing is not None:
                    return False
            _logger.warning(
                "table_create_failed",
                table=self._table_name,
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
            )
            raise
        else:
            return True

    async def try_batch_transaction(self, operations: list[_TransactionEntity]) -> bool:
        """Map adapter operations to ``submit_transaction`` with ETag guards.

        Returns False only for ``UpdateConditionNotSatisfied`` (412) on a guarded
        balance/reservation write and ``EntityAlreadyExists`` (409) on a reservation Create,
        matched on error code *and* failing operation index; every other error
        is raised so the credit store fails closed.
        """
        from azure.core.exceptions import HttpResponseError
        from azure.data.tables import TableTransactionError

        batch: list[Any] = [_map_operation(op) for op in operations]
        try:
            await self._get_client().submit_transaction(batch)
        except TableTransactionError as exc:
            code = _error_code(exc)
            index = _transaction_index(exc)
            target = (
                operations[index] if index is not None and 0 <= index < len(operations) else None
            )
            if (
                code == "UpdateConditionNotSatisfied"
                and target is not None
                and (target.row_key == _BALANCE_ROW_KEY or target.row_key.startswith("req-"))
                and target.operation in ("Update", "UpdateMerge", "Delete")
                and target.etag is not None
            ):
                return False
            if (
                code == "EntityAlreadyExists"
                and target is not None
                and target.operation == "Create"
                and target.row_key.startswith("req-")
            ):
                return False
            _logger.warning(
                "table_transaction_failed",
                table=self._table_name,
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
            )
            raise
        except HttpResponseError:
            raise
        else:
            return True

    async def probe_reachable(
        self,
        partition_key: str,
        row_key: str,
        *,
        timeout_seconds: float = 5.0,
        require_entity: bool = False,
    ) -> bool:
        """Bounded reachability probe for readiness (one read, cached by callers).

        Returns True when the table is reachable (row present or row absent),
        False for a missing table, missing RBAC (403), or timeout. Only the
        check name is surfaced by readiness; errors are logged by type only.
        """
        import asyncio as _asyncio

        from azure.core.exceptions import ResourceNotFoundError

        try:
            # Use the SDK client directly to avoid get_entity's exception handling
            await _asyncio.wait_for(
                self._get_client().get_entity(partition_key=partition_key, row_key=row_key),
                timeout=timeout_seconds,
            )
        except Exception as exc:
            code = _error_code(exc)
            if code == "TableNotFound":
                _logger.warning(
                    "table_probe_failed",
                    table=self._table_name,
                    error_type=type(exc).__name__,
                    status_code=getattr(exc, "status_code", None),
                )
                return False
            if isinstance(exc, ResourceNotFoundError):
                if require_entity:
                    _logger.warning(
                        "table_probe_entity_missing",
                        table=self._table_name,
                        error_type=type(exc).__name__,
                        status_code=getattr(exc, "status_code", None),
                    )
                    return False
                return True
            _logger.warning(
                "table_probe_failed",
                table=self._table_name,
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
            )
            return False
        else:
            return True

    async def query_entities(
        self, partition_key: str, row_key_prefix: str | None = None
    ) -> list[Mapping[str, Any]]:
        """Partition scan with a parameterised RowKey range for the prefix."""
        client = self._get_client()
        if row_key_prefix:
            upper = prefix_upper_bound(row_key_prefix)
            query_filter = "PartitionKey eq @pk and RowKey ge @lo and RowKey lt @hi"
            parameters = {"pk": partition_key, "lo": row_key_prefix, "hi": upper}
        else:
            query_filter = "PartitionKey eq @pk"
            parameters = {"pk": partition_key}
        try:
            return [
                normalise_entity(entity)
                async for entity in client.query_entities(query_filter, parameters=parameters)
            ]
        except Exception as exc:
            _logger.warning(
                "table_query_failed",
                table=self._table_name,
                error_type=type(exc).__name__,
            )
            raise


class TableEntityMissingEtagError(RuntimeError):
    """A balance Update/Delete arrived without an ETag and was refused."""


def _error_code(exc: Exception) -> str | None:
    for candidate in (
        getattr(exc, "error_code", None),
        getattr(getattr(exc, "error", None), "code", None),
    ):
        if candidate is not None:
            try:
                # Handle enum values by extracting .value if available
                if hasattr(candidate, "value"):
                    return str(candidate.value)
                return str(candidate)
            except Exception:
                continue
    # Fall back to message parsing so real service errors still map correctly.
    message = str(getattr(exc, "message", exc) or "")
    for known in ("UpdateConditionNotSatisfied", "EntityAlreadyExists", "TableNotFound"):
        if known in message:
            return known
    return None


def _transaction_index(exc: Exception) -> int | None:
    """Only trust an operation index explicitly included in the service message."""
    import re

    match = re.match(r"^\s*(\d+):", str(getattr(exc, "message", "")))
    return int(match.group(1)) if match else None


__all__ = [
    "AzureTableEntityClient",
    "TableEntityMissingEtagError",
    "normalise_entity",
    "prefix_upper_bound",
    "select_credential",
]
