"""Owned signed-turn preparation and validation before candidate reservations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.google_history import carrier_tokens, project_history
from foundry_router.api.google_state import (
    ProviderStateError,
    SealedTurn,
    StateBinding,
    StateCodec,
    canonical_bytes,
    check_state_deadline,
    framed_digest,
)


@dataclass(frozen=True, repr=False)
class PreparedContinuation:
    """Contains no credentials, prompts, results or visible generated content."""

    backend: str
    request_digest: str
    turns: tuple[SealedTurn, ...]
    signature_input_tokens: int

    def validate(self, body: dict[str, Any]) -> None:
        if framed_digest("context", body) != self.request_digest:
            raise ProviderStateError("Invalid provider state")


def unsigned_native_part(item: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct exactly one structurally projected signed text/function Part."""
    if item["type"] == "function_call":
        try:
            args = load_bounded_json(item["arguments"])
        except ValueError:
            raise ProviderStateError("Invalid provider state") from None
        if not isinstance(args, dict):
            raise ProviderStateError("Invalid provider state")
        return {"functionCall": {"id": item["call_id"], "name": item["name"], "args": args}}
    if item["type"] == "message" and item.get("role") == "assistant":
        return {"text": item["content"][0]["text"]}
    raise ProviderStateError("Invalid provider state")


def prepare_continuation(
    body: dict[str, Any],
    codec: StateCodec,
    bindings: dict[str, StateBinding],
    *,
    now: int,
    deadline: float | None = None,
) -> PreparedContinuation | None:
    """Structural validation supplements required ordinary adapter validation.

    Capture request identity before any await. Only configured binding identities can decrypt;
    public token payloads cannot select arbitrary backends or construct owned preparation.
    """
    tokens = carrier_tokens(body)
    projected, digests = project_history(body, deadline=deadline)
    snapshot = framed_digest("context", body)
    if not tokens:
        return None
    # Each key/binding attempt remains bounded by a configured pool. No provider calls.
    if not 1 <= len(bindings) <= 256:
        raise ProviderStateError("Invalid provider state")
    unique = tuple(dict.fromkeys(tokens))
    turns: dict[str, SealedTurn] = {}
    selected = None
    for token in unique:
        check_state_deadline(deadline)
        backend, turn = codec.open_bound(
            token, bindings if selected is None else {selected: bindings[selected]}, now=now
        )
        selected = backend
        turns[token] = turn
    occupied: set[int] = set()
    last_end = 0
    signature_tokens = 0
    for token, turn in turns.items():
        check_state_deadline(deadline)
        end = turn.start + len(turn.item_ids)
        if turn.start < last_end or end > len(projected) or turn.history != digests[end - 1]:
            raise ProviderStateError("Invalid provider state")
        for offset, identity in enumerate(turn.item_ids):
            index = turn.start + offset
            item = projected[index]
            carrier = body["input"][index].get("foundry_provider_state")
            if item.get("id") != identity or carrier != {"version": 1, "token": token}:
                raise ProviderStateError("Invalid provider state")
            if framed_digest("part", unsigned_native_part(item)) != turn.parts[offset]:
                raise ProviderStateError("Invalid provider state")
            occupied.add(index)
        last_end = end
        signature_tokens += sum(
            len(signature) + 64 for signature in turn.signatures if signature is not None
        )
    expected = {
        index
        for index, item in enumerate(projected)
        if item["type"] == "function_call" or item.get("role") == "assistant"
    }
    if occupied != expected or selected is None:
        raise ProviderStateError("Invalid provider state")
    return PreparedContinuation(selected, snapshot, tuple(turns.values()), signature_tokens)


def seal_output_turn(
    body: dict[str, Any],
    output: list[dict[str, Any]],
    signatures: tuple[str | None, ...],
    codec: StateCodec,
    binding: StateBinding,
    *,
    response_id: str,
    now: int,
    max_history_items: int,
    max_result_bytes: int,
) -> list[dict[str, Any]]:
    """Seal only API-validated completed STOP items with prospective replay headroom.

    Caller retains finish/schema/usage validation responsibility. No partial caller output is
    mutated or exposed if state or prospective intake admission cannot fit.
    """
    projected, _ = project_history(body)
    full = {**body, "input": [*projected, *output]}
    items, digests = project_history(full)
    if not output or len(signatures) != len(output):
        raise ProviderStateError("Invalid provider state")
    start = len(projected)
    calls = sum(item.get("type") == "function_call" for item in output)
    if calls and not any(signatures):
        raise ProviderStateError("Invalid provider state")
    turn = SealedTurn(
        response_id=response_id,
        start=start,
        item_ids=tuple(item["id"] for item in items[start:]),
        history=digests[-1],
        parts=tuple(framed_digest("part", unsigned_native_part(item)) for item in items[start:]),
        signatures=signatures,
    )
    token = codec.seal(binding, turn, now=now)
    carrier = {"version": 1, "token": token}
    if len(canonical_bytes(carrier)) * len(output) > 262144:
        raise ProviderStateError("Invalid provider state")
    finalized = [{**item, "foundry_provider_state": carrier} for item in items[start:]]
    replay = {**body, "input": [*body["input"], *finalized]}
    carrier_tokens(replay)
    headroom = calls * (max_result_bytes * 6 + 512) if calls else 65536 * 6 + 512
    if (
        len(replay["input"]) + max(calls, 1) > max_history_items
        or len(canonical_bytes(replay)) + headroom + 256 > 2097152
        or len(canonical_bytes(finalized, max_bytes=4194304)) > 4194304
    ):
        raise ProviderStateError("Invalid provider state")
    return finalized
