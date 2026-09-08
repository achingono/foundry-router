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
