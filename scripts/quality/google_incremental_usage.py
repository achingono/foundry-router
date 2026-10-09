"""Verifier-only bounded SSE usage observation and monotonic remaining-budget debits."""

from __future__ import annotations

from google_live_budget import TOKEN_LIMIT, locked, write_atomic

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.backends import MAX_GOOGLE_RESPONSE_BYTES

MAX_FRAME_BYTES = 1024 * 1024
MAX_INPUT_TOKENS = 64
MAX_OUTPUT_TOKENS = 1024
MAX_TOTAL_TOKENS = MAX_INPUT_TOKENS + MAX_OUTPUT_TOKENS
NEWLINE = 10


class IncrementalUsage:
    """Retain numeric maxima only; caller persists changes before forwarding chunks."""

    def __init__(self):
        self.line = bytearray()
        self.data = []
        self.frame_bytes = 0
        self.total_bytes = 0
        self.input_tokens = None
        self.output_tokens = None
        self.total_tokens = None
        self.thought_tokens = None
        self.final_usage = None
        self.invalid = False
        self.overrun = False
        self.done = False
        self.finish_reason = False
        self.eof = False

    @property
    def maximum_tokens(self):
        known = [value for value in (self.total_tokens,) if value is not None]
        if any(
            value is not None
            for value in (self.input_tokens, self.output_tokens, self.thought_tokens)
        ):
            known.append(
                (self.input_tokens or 0) + max(self.output_tokens or 0, self.thought_tokens or 0)
            )
        return max(known) if known else None

    @property
    def terminal_usage(self):
        return (
            self.eof
            and self.done
            and self.finish_reason
            and not self.invalid
            and not self.overrun
            and self.final_usage is not None
            and self.final_usage[0] == self.input_tokens
            and self.final_usage[1] == self.output_tokens
            and self.final_usage[2] == self.total_tokens
        )

    def feed(self, chunk):
        self.total_bytes += len(chunk)
        if self.total_bytes > MAX_GOOGLE_RESPONSE_BYTES:
            self.invalid = True
            raise ValueError("Verification response bound")
        # Process lines incrementally: frame bounds also cover comments/non-data lines.
        for value in chunk:
            self.frame_bytes += 1
            if self.frame_bytes > MAX_FRAME_BYTES:
                self.invalid = True
                raise ValueError("Verification frame bound")
            if value == NEWLINE:
                line = bytes(self.line).removesuffix(b"\r")
                self.line.clear()
                if not line:
                    self._event()
                    self.data.clear()
                    self.frame_bytes = 0
                elif line.startswith(b"data:"):
                    self.data.append(line[5:].removeprefix(b" "))
            else:
                self.line.append(value)

    def finish(self):
        self.eof = True
        if self.line or self.data or self.frame_bytes:
            self.invalid = True

    def _event(self):
        if not self.data:
            return
        payload = b"\n".join(self.data)
        if payload == b"[DONE]":
            if self.done:
                self.invalid = True
            self.done = True
            return
        if self.done:
            self.invalid = True
        try:
            event = load_bounded_json(payload.decode(), max_bytes=MAX_FRAME_BYTES)
        except (ValueError, UnicodeError):
            self.invalid = True
            return
        if not isinstance(event, dict):
            self.invalid = True
            return
        choices = event.get("choices")
        if isinstance(choices, list):
            self.finish_reason |= any(
                isinstance(choice, dict) and choice.get("finish_reason") == "stop"
                for choice in choices
            )
        usage = event.get("usage")
        if usage is None:
            return
        if not isinstance(usage, dict):
            self.invalid = True
            return
        self._usage(usage, final=choices == [])

    def _usage(self, usage, *, final):
        counts = []
        for field, attribute, maximum in (
            ("prompt_tokens", "input_tokens", MAX_INPUT_TOKENS),
            ("completion_tokens", "output_tokens", MAX_OUTPUT_TOKENS),
            ("total_tokens", "total_tokens", MAX_TOTAL_TOKENS),
        ):
            value = usage.get(field)
            if value is None:
                counts.append(None)
                continue
            if type(value) is not int or value < 0:
                self.invalid = True
                counts.append(None)
                continue
            # Numeric evidence is bounded by the wire/frame; preserve actual overrun.
            old = getattr(self, attribute)
            if old is not None and value < old:
                self.invalid = True
            setattr(self, attribute, max(old or 0, value))
            self.overrun |= value > maximum
            counts.append(value)
        self._thoughts(usage.get("completion_tokens_details"), counts[1])
        if all(value is not None for value in counts):
            if counts[2] != counts[0] + counts[1]:
                self.invalid = True
            elif final:
                self.final_usage = tuple(counts)
        if self.maximum_tokens is not None:
            self.overrun |= self.maximum_tokens > MAX_TOTAL_TOKENS

    def _thoughts(self, details, output):
        if details is not None and not isinstance(details, dict):
            self.invalid = True
        thought = details.get("reasoning_tokens") if isinstance(details, dict) else None
        if thought is not None:
            if type(thought) is not int or thought < 0:
                self.invalid = True
            else:
                self.thought_tokens = max(self.thought_tokens or 0, thought)
                self.overrun |= thought > MAX_OUTPUT_TOKENS
                if output is None or thought > output:
                    self.invalid = True


def record_progress(ledger, baseline, allowed, project, case_id, tokens, *, overrun=False):  # noqa: PLR0913, PLR0917 -- explicit audit inputs
    """Raise observed usage only for this stage's reserved cases, preserving old debits."""
    if type(tokens) is not int or tokens < 0 or type(overrun) is not bool:
        raise ValueError("Invalid verification usage")
    if (project, case_id) not in allowed:
        raise ValueError("Invalid verification case")
    with locked(ledger.path):
        current = ledger._read()
        if current["session"] != baseline["session"]:
            raise ValueError("Invalid verification baseline")
        for owner, previous in baseline["projects"].items():
            live = current["projects"][owner]
            if any(live["cases"].get(key) != value for key, value in previous["cases"].items()):
                raise ValueError("Historical verification debit changed")
            if any(
                (owner, key) not in allowed
                for key in live["cases"].keys() - previous["cases"].keys()
            ):
                raise ValueError("Unexpected verification debit")
            if live["requests"] < previous["requests"] or live["tokens"] < previous["tokens"]:
                raise ValueError("Historical verification budget lowered")
            if previous["halted"] and not live["halted"]:
                raise ValueError("Historical verification halt removed")
        if case_id in baseline["projects"][project]["cases"]:
            raise ValueError("Historical verification case forbidden")
        item = current["projects"][project]
        case = item["cases"].get(case_id)
        if case is None or case["reserved_tokens"] != MAX_TOTAL_TOKENS:
            raise ValueError("Verification reservation missing")
        previous_usage = case["actual_tokens"]
        if previous_usage is not None and tokens < previous_usage:
            raise ValueError("Verification usage lowered")
        previous_debit = max(case["reserved_tokens"], previous_usage or 0)
        case["actual_tokens"] = tokens
        item["tokens"] += max(case["reserved_tokens"], tokens) - previous_debit
        item["halted"] |= overrun or tokens > MAX_TOTAL_TOKENS or item["tokens"] > TOKEN_LIMIT
        write_atomic(ledger.path, current)
