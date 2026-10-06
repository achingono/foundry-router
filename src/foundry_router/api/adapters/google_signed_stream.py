"""Bounded public SSE emitted only after a complete native signed response is sealed."""

from __future__ import annotations

import copy
import json
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.google_state import ProviderStateError
from foundry_router.api.google_work import bounded_signed_work

if TYPE_CHECKING:
    from foundry_router.api.adapters.google_signed import GoogleSignedAdapter


@dataclass(frozen=True, repr=False)
class SignedStreamResult:
    events: tuple[bytes, ...]
    sequence: int
    event_bytes: int
    usage: tuple[int | None, int | None]
    response_id: str
    terminal_event: bytes | None
    meaningful_output: bool


class GoogleSignedStreamDecoder:
    """Consumes generateContent JSON, never guesses native SSE Part identities."""

    finish_at_prefetch_eof = True

    def __init__(
        self, adapter: GoogleSignedAdapter, body: dict[str, Any], logical_model: str
    ) -> None:
        self.adapter = adapter
        self.body = body
        self.logical_model = logical_model
        self.raw = bytearray()
        self.sequence = 0
        self.event_bytes = 0
        self.usage: tuple[int | None, int | None] = (None, None)
        self.meaningful_output = False
        self.finished = False
        self.prefetch_finished = False
        self.terminal_sent = False
        self.response_id = "resp_" + uuid.uuid4().hex[:24]
        self.terminal_event: bytes | None = None

    def feed(self, chunk: bytes) -> list[bytes]:
        if self.finished or len(self.raw) + len(chunk) > 4194304:
            self.raw.clear()
            self.finished = True
            raise ProviderStateError("Invalid provider state")
        self.raw.extend(chunk)
        return []

    def _event(self, kind: str, **fields: Any) -> bytes:
        event = {"type": kind, "sequence_number": self.sequence, **fields}
        self.sequence += 1
        wire = (
            "data: " + json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n\n"
        ).encode()
        self.event_bytes += len(wire)
        if len(wire) > 4194304 or self.event_bytes > 8388608:
            raise ProviderStateError("Invalid provider state")
        return wire

    def finish(self) -> list[bytes]:
        if self.finished:
            raise ProviderStateError("Invalid provider state")
        self.finished = True
        try:
            upstream = load_bounded_json(self.raw.decode("utf-8"), max_bytes=4194304)
        except (ValueError, UnicodeError):
            raise ProviderStateError("Invalid provider state") from None
        finally:
            self.raw.clear()
        self.usage = self.adapter.extract_usage("responses", upstream)
        return self._finish_upstream(upstream)

    async def finish_owned(self, *, deadline: float) -> list[bytes]:
        if self.finished:
            raise ProviderStateError("Invalid provider state")
        self.finished = True
        # Capture known usage before scheduling; transport owns this snapshot on
        # saturation/timeout/cancellation. Only local worker state mutates below.
        try:
            upstream = load_bounded_json(self.raw.decode("utf-8"), max_bytes=4194304)
        except (ValueError, UnicodeError):
            raise ProviderStateError("Invalid provider state") from None
        finally:
            self.raw.clear()
        self.usage = self.adapter.extract_usage("responses", upstream)
        local = copy.copy(self)
        local.raw = bytearray()

        def finalize() -> SignedStreamResult:
            events = local._finish_upstream(upstream)
            return SignedStreamResult(
                tuple(events),
                local.sequence,
                local.event_bytes,
                local.usage,
                local.response_id,
                local.terminal_event,
                local.meaningful_output,
            )

        result = await bounded_signed_work(
            finalize, deadline=deadline, lease=self.adapter.seal_context.work_lease
        )
        # No await between publication and handing the result to prefetch. A
        # cancelled/expired worker never publishes to transport-owned state.
        if self.terminal_sent:
            raise ProviderStateError("Invalid provider state")
        self.sequence = result.sequence
        self.event_bytes = result.event_bytes
        self.usage = result.usage
        self.response_id = result.response_id
        self.terminal_event = result.terminal_event
        self.meaningful_output = result.meaningful_output
        return list(result.events)

    def _finish_upstream(self, upstream: Any) -> list[bytes]:
        translated = self.adapter.translate_success(
            "responses",
            upstream,
            logical_model=self.logical_model,
            request_body=self.body,
            metadata=self.body.get("metadata"),
        )
        response = translated.body
        self.response_id = response["id"]
        events = [
            self._event(
                "response.created",
                response={
                    **response,
                    "output": [],
                    "status": "in_progress",
                    "usage": None,
                    "incomplete_details": None,
                    "error": None,
                },
            )
        ]
        for index, item in enumerate(response["output"]):
            added = {**item, "status": "in_progress"}
            added.pop("foundry_provider_state", None)
            if item["type"] == "function_call":
                added["arguments"] = ""
                events.append(
                    self._event("response.output_item.added", output_index=index, item=added)
                )
                events.append(
                    self._event(
                        "response.function_call_arguments.delta",
                        output_index=index,
                        item_id=item["id"],
                        delta=item["arguments"],
                    )
                )
                events.append(
                    self._event(
                        "response.function_call_arguments.done",
                        output_index=index,
                        item_id=item["id"],
                        arguments=item["arguments"],
                    )
                )
            else:
                added["content"] = []
                events.append(
                    self._event("response.output_item.added", output_index=index, item=added)
                )
                for content_index, part in enumerate(item["content"]):
                    field = "text" if part["type"] == "output_text" else "refusal"
                    prefix = "response.output_text" if field == "text" else "response.refusal"
                    events.append(
                        self._event(
                            "response.content_part.added",
                            output_index=index,
                            item_id=item["id"],
                            content_index=content_index,
                            part={**part, field: ""},
                        )
                    )
                    events.append(
                        self._event(
                            prefix + ".delta",
                            output_index=index,
                            item_id=item["id"],
                            content_index=content_index,
                            delta=part[field],
                        )
                    )
                    events.append(
                        self._event(
                            prefix + ".done",
                            output_index=index,
                            item_id=item["id"],
                            content_index=content_index,
                            **{field: part[field]},
                        )
                    )
                    events.append(
                        self._event(
                            "response.content_part.done",
                            output_index=index,
                            item_id=item["id"],
                            content_index=content_index,
                            part=part,
                        )
                    )
            events.append(self._event("response.output_item.done", output_index=index, item=item))
        terminal = (
            "response.completed" if response["status"] == "completed" else "response.incomplete"
        )
        events.append(self._event(terminal, response=response))
        self.terminal_event = events[-1]
        if sum(len(event) for event in events) > 8388608:
            raise ProviderStateError("Invalid provider state")
        self.meaningful_output = True
        return events

    def mark_delivered(self, event: bytes) -> None:
        if event is self.terminal_event:
            self.terminal_sent = True

    def build_failure(self, message: str) -> list[bytes]:
        _ = message  # Never echo provider/exception content into public errors.
        self.raw.clear()
        if self.terminal_sent:
            return []
        self.terminal_sent = True
        self.event_bytes = 0
        return [
            self._event(
                "response.failed",
                response={
                    "id": self.response_id,
                    "object": "response",
                    "created_at": int(time.time()),
                    "model": self.logical_model,
                    "status": "failed",
                    "output": [],
                    "error": {"code": "upstream_error", "message": "Upstream stream failed"},
                    "parallel_tool_calls": False,
                    "tool_choice": "auto",
                    "tools": [],
                    "metadata": {},
                },
            )
        ]
