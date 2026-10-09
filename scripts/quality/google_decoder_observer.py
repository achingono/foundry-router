"""Existing adapter validates wire termination; numeric usage remains independent."""

from __future__ import annotations

from google_incremental_usage import MAX_FRAME_BYTES, IncrementalUsage

from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter
from foundry_router.api.adapters.google_schema import load_bounded_json


class DecoderObserver(IncrementalUsage):
    def __init__(self, *, prompt):
        super().__init__()
        self.mirror = GoogleAiStudioAdapter().create_stream_decoder(
            logical_model="m",
            request_body={"input": prompt, "max_output_tokens": 1024, "stream": True},
        )
        self.mirror_terminal = False
        self.mirror_valid = False

    def feed(self, chunk):
        # Numeric maxima survive even when the provider's output envelope is invalid.
        super().feed(chunk)
        try:
            self._discard(self.mirror.feed(chunk))
        except ValueError:
            self.invalid = True
            raise

    def _event(self):
        if not self.data:
            return
        payload = b"\n".join(self.data)
        if payload == b"[DONE]":
            self.invalid |= self.done
            self.done = True
            return
        self.invalid |= self.done
        try:
            event = load_bounded_json(payload.decode(), max_bytes=MAX_FRAME_BYTES)
        except (ValueError, UnicodeError):
            self.invalid = True
            return
        if not isinstance(event, dict):
            self.invalid = True
            return
        usage = event.get("usage")
        if isinstance(usage, dict):
            self._usage(usage, final=False)
        elif usage is not None:
            self.invalid = True

    def _discard(self, events):
        for event in events:
            payload = next(line[6:] for line in event.splitlines() if line.startswith(b"data: "))
            kind = load_bounded_json(payload.decode(), max_bytes=MAX_FRAME_BYTES)["type"]
            if kind == "response.completed":
                self.mirror_terminal = True
            if kind in {"response.failed", "response.incomplete"}:
                self.invalid = True

    def finish(self):
        super().finish()
        try:
            self._discard(self.mirror.finish())
            self.mirror_valid = self.mirror.validated and self.mirror_terminal and not self.invalid
        except ValueError:
            self.invalid = True
            raise

    @property
    def complete_usage(self):
        return (
            type(self.input_tokens) is int
            and type(self.output_tokens) is int
            and type(self.total_tokens) is int
            and self.total_tokens == self.input_tokens + self.output_tokens
            and self.maximum_tokens == self.total_tokens
            and (self.thought_tokens is None or self.thought_tokens <= self.output_tokens)
            and not self.invalid
            and not self.overrun
        )

    @property
    def terminal_usage(self):
        return self.complete_usage and self.done and self.eof and self.mirror_valid

    def clear(self):
        # Do not finish a cancelled mirror; release all assembled output/context.
        self.mirror = None
        self.line.clear()
        self.data.clear()

    def evidence(self):
        return {
            "mirror_terminal_valid": self.mirror_valid,
            "complete_usage": self.complete_usage,
            "decoded_done": self.done,
            "upstream_eof": self.eof,
            "mirror_terminal_seen": self.mirror_terminal,
        }
