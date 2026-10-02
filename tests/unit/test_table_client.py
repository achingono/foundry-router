"""Phase 11: concrete Table client mapping tests (fakes + real SDK error types)."""

from __future__ import annotations

import pytest

from foundry_router.state.azure import (
    AzureTableEntityClient,
    TableEntityMissingEtagError,
    normalise_entity,
    prefix_upper_bound,
)
from foundry_router.state.table import _TransactionEntity


def _balance_update(etag: str | None) -> _TransactionEntity:
    return _TransactionEntity(
        partition_key="b1",
        row_key="balance",
        operation="Update",
        entity={"PartitionKey": "b1", "RowKey": "balance"},
        etag=etag,
    )


def _reservation_create() -> _TransactionEntity:
    return _TransactionEntity(
        partition_key="b1",
        row_key="req-r1",
        operation="Create",
        entity={"PartitionKey": "b1", "RowKey": "req-r1"},
    )


class _FakeAioClient:
    """Minimal async TableClient double with injectable behaviour."""

    def __init__(self) -> None:
        self.submitted: list | None = None
        self.submit_error: Exception | None = None
        self.created: list[dict] = []
        self.create_error: Exception | None = None
        self.query_calls: list[tuple[str, dict]] = []

    async def submit_transaction(self, batch):
        self.submitted = list(batch)
        if self.submit_error is not None:
            raise self.submit_error
        return [{} for _ in batch]

    async def create_entity(self, entity):
        self.created.append(dict(entity))
        if self.create_error is not None:
            raise self.create_error
        return dict(entity)

    def query_entities(self, filt, parameters=None):
        self.query_calls.append((filt, dict(parameters or {})))

        async def _gen():
            return
            yield  # pragma: no cover - empty generator

        return _gen()

    async def close(self):
        return None


def _client_with(fake: _FakeAioClient) -> AzureTableEntityClient:
    client = AzureTableEntityClient(
        endpoint="https://placeholder.table.core.windows.net",
        table_name="routercredit",
        credential=object(),
    )
    client._client = fake  # noqa: SLF001 - inject double to avoid network
    return client


def test_normalise_entity_bridges_sdk_metadata_etag() -> None:
    entity = {"PartitionKey": "b1", "RowKey": "balance", "metadata": {"etag": "W/abc"}}
    assert normalise_entity(entity)["odata.etag"] == "W/abc"


def test_normalise_entity_keeps_existing_odata_etag() -> None:
    entity = {"PartitionKey": "b1", "RowKey": "balance", "odata.etag": "W/keep"}
    assert normalise_entity(entity)["odata.etag"] == "W/keep"


def test_prefix_upper_bound_excludes_prefix_sibling() -> None:
    assert prefix_upper_bound("req-") == "req."
    assert "req-anything" < prefix_upper_bound("req-")


@pytest.mark.asyncio
async def test_balance_update_without_etag_fails_closed() -> None:
    client = _client_with(_FakeAioClient())
    with pytest.raises(TableEntityMissingEtagError):
        await client.try_batch_transaction([_balance_update(None)])


@pytest.mark.asyncio
async def test_balance_412_maps_to_false_on_expected_operation() -> None:
    from azure.data.tables import TableTransactionError

    fake = _FakeAioClient()
    err = TableTransactionError(message="0: The update condition is not satisfied.")
    err.error_code = "UpdateConditionNotSatisfied"  # type: ignore[attr-defined]
    fake.submit_error = err
    client = _client_with(fake)
    assert await client.try_batch_transaction([_balance_update("W/1")]) is False


@pytest.mark.asyncio
async def test_reservation_409_maps_to_false_on_create() -> None:
    from azure.data.tables import TableTransactionError

    fake = _FakeAioClient()
    err = TableTransactionError(message="0: The specified entity already exists.")
    err.error_code = "EntityAlreadyExists"  # type: ignore[attr-defined]
    fake.submit_error = err
    # Failing index 0 targets the single create op in this batch.
    client = _client_with(fake)
    assert await client.try_batch_transaction([_reservation_create()]) is False


@pytest.mark.asyncio
async def test_unexpected_error_code_raises_fail_closed() -> None:
    from azure.data.tables import TableTransactionError

    fake = _FakeAioClient()
    err = TableTransactionError(message="0: Internal error.")
    err.error_code = "InternalError"  # type: ignore[attr-defined]
    fake.submit_error = err
    client = _client_with(fake)
    with pytest.raises(TableTransactionError):
        await client.try_batch_transaction([_balance_update("W/1")])


@pytest.mark.asyncio
async def test_409_on_balance_update_raises() -> None:
    """A 409 on an unexpected operation must not be masked as a conflict."""
    from azure.data.tables import TableTransactionError

    fake = _FakeAioClient()
    err = TableTransactionError(message="0: Entity already exists.")
    err.error_code = "EntityAlreadyExists"  # type: ignore[attr-defined]
    fake.submit_error = err
    client = _client_with(fake)
    with pytest.raises(TableTransactionError):
        await client.try_batch_transaction([_balance_update("W/1")])


@pytest.mark.asyncio
async def test_query_uses_parameterised_prefix_range() -> None:
    fake = _FakeAioClient()
    client = _client_with(fake)
    await client.query_entities("b1", "req-")
    assert fake.query_calls
    filt, params = fake.query_calls[0]
    assert "@pk" in filt and "@lo" in filt and "@hi" in filt
    assert params == {"pk": "b1", "lo": "req-", "hi": "req."}
    assert "req-" not in filt.replace("@lo", "")


@pytest.mark.asyncio
async def test_try_create_false_on_exists() -> None:
    from azure.core.exceptions import HttpResponseError

    fake = _FakeAioClient()
    err = HttpResponseError(message="EntityAlreadyExists: exists")
    err.error_code = "EntityAlreadyExists"  # type: ignore[attr-defined]
    fake.create_error = err
    client = _client_with(fake)
    assert await client.try_create_entity({"PartitionKey": "b1", "RowKey": "balance"}) is False
