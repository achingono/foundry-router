"""Shared-state adapter boundaries."""

from foundry_router.state.table import (
    AzureTableHealthStore,
    TableEntityClient,
    TableEntityWriteError,
)

__all__ = ["AzureTableHealthStore", "TableEntityClient", "TableEntityWriteError"]
