"""Shared-state adapter boundaries."""

from foundry_router.state.table import (
    AzureTableCreditStore,
    AzureTableHealthStore,
    TableEntityClient,
    TableEntityCreditStoreError,
    TableEntityWriteError,
    _TransactionEntity,
)

__all__ = [
    "AzureTableCreditStore",
    "AzureTableHealthStore",
    "TableEntityClient",
    "TableEntityCreditStoreError",
    "TableEntityWriteError",
    "_TransactionEntity",
]

# NOTE: `foundry_router.state.azure` (concrete SDK client) is imported lazily
# by consumers so `state.table` stays importable without Azure dependencies.
