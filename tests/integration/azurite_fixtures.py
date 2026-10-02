"""Azurite-backed integration test fixtures and adapter (Phase 11).

These fixtures use real Azure SDK credentials against the local Azurite emulator.
They never reach production code and are only used in tests marked with @pytest.mark.azurite.
"""

from __future__ import annotations

import uuid
from contextlib import suppress

from azure.core.credentials import AzureNamedKeyCredential
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableServiceClient

from foundry_router.state.azure import AzureTableEntityClient

# Azurite well-known local account
_AZURITE_ACCOUNT = "devstoreaccount1"
_AZURITE_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)
_AZURITE_ENDPOINT = "http://127.0.0.1:10002/devstoreaccount1"


def azurite_available() -> bool:
    """Check if Azurite Table endpoint is reachable."""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 10002), timeout=1):
            return True
    except Exception:
        return False


def azurite_credential() -> AzureNamedKeyCredential:
    """Named-key credential for Azurite."""
    return AzureNamedKeyCredential(_AZURITE_ACCOUNT, _AZURITE_KEY)


def azurite_endpoint() -> str:
    """Table endpoint for Azurite."""
    return _AZURITE_ENDPOINT


def azurite_connection_string() -> str:
    """Full connection string for Azurite (used by TableServiceClient for table mgmt)."""
    return (
        "DefaultEndpointsProtocol=http;"
        "AccountName=devstoreaccount1;"
        f"AccountKey={_AZURITE_KEY};"
        f"TableEndpoint={_AZURITE_ENDPOINT};"
    )


async def azurite_create_tables(*table_names: str) -> None:
    """Create tables in Azurite (idempotent)."""
    tsc = TableServiceClient.from_connection_string(azurite_connection_string())
    for name in table_names:
        with suppress(ResourceExistsError):
            tsc.create_table(name)
    tsc.close()


async def azurite_delete_tables(*table_names: str) -> None:
    """Delete tables from Azurite."""
    tsc = TableServiceClient.from_connection_string(azurite_connection_string())
    for name in table_names:
        with suppress(ResourceNotFoundError):
            tsc.delete_table(name)
    tsc.close()


async def azurite_client(table_name: str) -> AzureTableEntityClient:
    """Construct a real AzureTableEntityClient pointed at Azurite.

    The client allows HTTP for local testing and uses the Azurite named-key credential.
    """
    return AzureTableEntityClient(
        endpoint=azurite_endpoint(),
        table_name=table_name,
        credential=azurite_credential(),
        request_timeout_seconds=5.0,
        allow_http_for_testing=True,
    )


class AzuriteFixture:
    """Async context manager for a clean Azurite test environment."""

    def __init__(self, *table_names: str) -> None:
        self.table_names = table_names
        self.clients: list[AzureTableEntityClient] = []

    @property
    def health_table(self) -> str:
        return self.table_names[0]

    @property
    def credit_table(self) -> str:
        return self.table_names[1]

    async def __aenter__(self) -> AzuriteFixture:
        await azurite_create_tables(*self.table_names)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        for client in self.clients:
            with suppress(Exception):
                await client.close()
        await azurite_delete_tables(*self.table_names)

    async def client(self, table_name: str) -> AzureTableEntityClient:
        client = await azurite_client(table_name)
        self.clients.append(client)
        return client


__all__ = [
    "AzuriteFixture",
    "azurite_available",
    "azurite_client",
    "azurite_connection_string",
    "azurite_create_tables",
    "azurite_credential",
    "azurite_delete_tables",
    "azurite_endpoint",
    "unique_table_names",
]


def unique_table_names() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:12]
    return f"rh{suffix}", f"rc{suffix}"
