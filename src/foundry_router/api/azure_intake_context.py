"""Immutable bounded response facts for isolated Azure prepared requests."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_CONTEXT_BYTES = 64 * 1024


class PreparedAzureResponsePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    backend_id: str
    provider: Literal["azure_anthropic", "azure_mai"]
    kind: Literal["text", "one_png"]

    @model_validator(mode="after")
    def policy_matches_provider(self) -> PreparedAzureResponsePolicy:
        if self.kind != ("one_png" if self.provider == "azure_mai" else "text"):
            raise ValueError("Invalid prepared response policy")
        return self


class PreparedAzureResponseContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: str
    operation: Literal["responses"]
    metadata: tuple[tuple[str, str], ...] = ()
    policies: tuple[PreparedAzureResponsePolicy, ...]

    @model_validator(mode="after")
    def bounded_context(self) -> PreparedAzureResponseContext:
        if (
            len(self.metadata) > 16
            or len(dict(self.metadata)) != len(self.metadata)
            or any(len(key) > 64 or len(value) > 512 for key, value in self.metadata)
            or not self.policies
            or len({item.backend_id for item in self.policies}) != len(self.policies)
            or len(self.model_dump_json().encode()) > MAX_CONTEXT_BYTES
        ):
            raise ValueError("Invalid bounded prepared response context")
        return self

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def for_backend(self, backend_id: str, provider: str) -> PreparedAzureResponsePolicy:
        for policy in self.policies:
            if policy.backend_id == backend_id and policy.provider == provider:
                return policy
        raise ValueError("Prepared response provider binding mismatch")

    def metadata_dict(self) -> dict[str, str]:
        return dict(self.metadata)
