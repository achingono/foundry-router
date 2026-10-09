"""Pure bounded function history and structured text contracts."""

from __future__ import annotations

import copy
import re
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.google_media import validate_inline_image
from foundry_router.api.adapters.google_raster import ImageWorkBudget
from foundry_router.api.adapters.google_schema import (
    load_bounded_json,
    validate_schema,
    validate_value,
)

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia
    from foundry_router.config.google_features import GoogleFeatureProfile

_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_MAX_ID_BYTES = 256
_MAX_DECLARATION_BYTES = 65536


def check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise ValueError("Request intake deadline exceeded")


def validate_identity(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > _MAX_ID_BYTES:
        raise ValueError("Invalid bounded tool call identity")
    return value


@dataclass(frozen=True)
class GoogleRequestContext:
    """A copied, request-local validation context; never stored on the shared adapter."""

    tools: dict[str, dict[str, Any]]
    choice: Any
    parallel: bool
    text_format: dict[str, Any] | None
    max_calls: int
    max_argument_bytes: int
    historical_ids: frozenset[str] = frozenset()
    stateless_signature_text: bool = False

    def validate_arguments(self, name: Any, arguments: Any) -> None:
        if not isinstance(name, str) or not isinstance(arguments, str):
            raise ValueError("Invalid function identity or argument shape")
        declaration = self.tools.get(name)
        if declaration is None:
            raise ValueError("Provider called an undeclared function")
        value = load_bounded_json(arguments, max_bytes=self.max_argument_bytes)
        if not isinstance(value, dict):
            raise ValueError("Function arguments must be a JSON object")
        if declaration["strict"]:
            validate_value(value, declaration["parameters"])

    def validate_calls(
        self, calls: list[dict[str, Any]], *, completed: bool, refusal: bool = False
    ) -> None:
        if len(calls) > self.max_calls or (not self.parallel and len(calls) > 1):
            raise ValueError("Provider exceeded the configured call count")
        identities: set[str] = set()
        for call in calls:
            identity = validate_identity(call.get("call_id"))
            name = call.get("name")
            if (
                identity in identities
                or identity in self.historical_ids
                or not isinstance(name, str)
                or not _NAME.fullmatch(name)
                or name not in self.tools
            ):
                raise ValueError("Invalid or duplicate provider function call")
            identities.add(identity)
            if completed:
                self.validate_arguments(call["name"], call["arguments"])
        if self.choice == "none" and calls:
            raise ValueError("Provider violated tool choice")
        if isinstance(self.choice, dict) and any(
            call["name"] != self.choice["name"] for call in calls
        ):
            raise ValueError("Provider violated named tool choice")
        if completed and isinstance(self.choice, dict) and not refusal and len(calls) != 1:
            raise ValueError("Named tool choice requires exactly one call")
        if (
            completed
            and not refusal
            and (self.choice == "required" or isinstance(self.choice, dict))
            and not calls
        ):
            raise ValueError("Provider omitted a required tool call")

    def validate_text(self, text: str, *, completed: bool, has_calls: bool) -> None:
        if not completed or self.text_format is None or (has_calls and not text):
            return
        value = load_bounded_json(text, max_bytes=4 * 1024 * 1024)
        if not isinstance(value, dict):
            raise ValueError("Structured text must be a JSON object")
        if self.text_format["type"] == "json_schema":
            validate_value(value, self.text_format["schema"])


def request_context(body: dict[str, Any], profile: GoogleFeatureProfile) -> GoogleRequestContext:
    declarations: dict[str, dict[str, Any]] = {}
    tools = body.get("tools", [])
    if not isinstance(tools, list) or len(tools) > profile.max_tools:
        raise ValueError("Function declarations exceed their bound")
    if len(str(tools).encode()) > _MAX_DECLARATION_BYTES:
        raise ValueError("Function declarations exceed their byte bound")
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) - {
            "type",
            "name",
            "description",
            "parameters",
            "strict",
        }:
            raise ValueError("Unsupported function declaration")
        name = tool.get("name")
        if (
            tool.get("type") != "function"
            or not isinstance(name, str)
            or not _NAME.fullmatch(name)
            or name in declarations
            or not isinstance(tool.get("strict"), bool)
            or ("description" in tool and not isinstance(tool["description"], str))
        ):
            raise ValueError("Function declarations require unique names and explicit strictness")
        validate_schema(tool.get("parameters"), strict=tool["strict"])
        declarations[name] = copy.deepcopy(tool)
    choice = body.get("tool_choice", "auto")
    if isinstance(choice, dict):
        if (
            set(choice) != {"type", "name"}
            or choice.get("type") != "function"
            or choice.get("name") not in declarations
        ):
            raise ValueError("Named tool choice must reference a declared function")
    elif not isinstance(choice, str) or choice not in {"auto", "none", "required"}:
        raise ValueError("Unsupported tool choice")
    if not declarations and (
        choice != "auto" or "tool_choice" in body or "parallel_tool_calls" in body
    ):
        raise ValueError("Tool choice requires function declarations")
    parallel = body.get("parallel_tool_calls", "parallel_calls" in profile.features)
    if not isinstance(parallel, bool) or (parallel and "parallel_calls" not in profile.features):
        raise ValueError("Parallel calls are not enabled")
    text_format = None
    if "text" in body:
        text = body["text"]
        if (
            not isinstance(text, dict)
            or set(text) != {"format"}
            or not isinstance(text["format"], dict)
        ):
            raise ValueError("Unsupported text format")
        text_format = text["format"]
        kind = text_format.get("type")
        if kind == "text" and set(text_format) == {"type"}:
            text_format = None
        elif kind == "json_object" and set(text_format) == {"type"}:
            pass
        elif kind == "json_schema" and not set(text_format) - {
            "type",
            "name",
            "schema",
            "strict",
            "description",
        }:
            if (
                not isinstance(text_format.get("name"), str)
                or not _NAME.fullmatch(text_format["name"])
                or text_format.get("strict") is not True
                or (
                    "description" in text_format and not isinstance(text_format["description"], str)
                )
            ):
                raise ValueError("Structured schemas require a name and strict true")
            validate_schema(text_format.get("schema"), strict=True)
        else:
            raise ValueError("Unsupported text format")
    return GoogleRequestContext(
        declarations,
        copy.deepcopy(choice),
        parallel,
        copy.deepcopy(text_format),
        profile.max_tools,
        profile.max_argument_bytes,
        frozenset(
            item["call_id"]
            for item in body.get("input", [])
            if isinstance(item, dict)
            and item.get("type") == "function_call"
            and isinstance(item.get("call_id"), str)
        )
        if isinstance(body.get("input"), list)
        else frozenset(),
    )


def requested_features(body: dict[str, Any], context: GoogleRequestContext) -> set[str]:
    features: set[str] = set()
    if "tools" in body or "tool_choice" in body or "parallel_tool_calls" in body:
        features.add("function_tools")
    if context.parallel and context.tools:
        features.add("parallel_calls")
    if context.text_format is not None:
        features.add(context.text_format["type"])
    historical_calls = 0
    for item in body.get("input", []) if isinstance(body.get("input"), list) else []:
        if isinstance(item, dict):
            if item.get("type") in {"function_call", "function_call_output"}:
                features.add("function_tools")
            if item.get("type") == "function_call":
                historical_calls += 1
                if historical_calls > 1:
                    features.add("parallel_calls")
            elif item.get("type") == "function_call_output" or item.get("role") != "assistant":
                historical_calls = 0
            content = item.get("content")
            if isinstance(content, list) and any(
                isinstance(part, dict) and part.get("type") == "input_image" for part in content
            ):
                features.add("inline_images")
            if isinstance(content, list) and any(
                isinstance(part, dict) and part.get("type") == "input_file" for part in content
            ):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "input_file":
                        uri = part.get("file_data")
                        features.add(
                            "inline_audio"
                            if isinstance(uri, str) and uri.startswith("data:audio/wav;base64,")
                            else "inline_video"
                            if isinstance(uri, str) and uri.startswith("data:video/avi;base64,")
                            else "inline_pdfs"
                        )
    return features


def build_messages(
    body: dict[str, Any],
    profile: GoogleFeatureProfile,
    context: GoogleRequestContext,
    *,
    deadline: float | None = None,
    preserve_assistant_order: bool = False,
    prepared_media: PreparedGoogleMedia | None = None,
) -> list[dict[str, Any]]:
    """Validate ordered, complete stateless turns while reconstructing Chat messages."""
    messages: list[dict[str, Any]] = []
    media_features = requested_features(body, context) & {
        "inline_pdfs",
        "inline_audio",
        "inline_video",
    }
    if media_features:
        if prepared_media is None or not media_features <= set(profile.features):
            raise ValueError("File media requires owned preparation")
        prepared_media.validate(body, profile)
    if body.get("instructions"):
        messages.append({"role": "system", "content": body["instructions"]})
    history = body.get("input")
    if isinstance(history, str):
        if not history.strip():
            raise ValueError("Input text must be nonempty")
        return [*messages, {"role": "user", "content": history}]
    if not isinstance(history, list) or not 1 <= len(history) <= profile.max_history_items:
        raise ValueError("Input history exceeds its item bound")
    pending: dict[str, dict[str, Any]] = {}
    all_ids: set[str] = set()
    result_phase = False
    image_count = 0
    image_bytes = 0
    image_work = ImageWorkBudget(jpeg_pixels=profile.max_jpeg_total_pixels)
    for item in history:
        check_deadline(deadline)
        if not isinstance(item, dict):
            raise ValueError("Input items must be objects")
        kind = item.get("type", "message")
        if kind == "function_call":
            if (
                set(item) - {"type", "id", "call_id", "name", "arguments", "status"}
                or item.get("status", "completed") != "completed"
                or result_phase
            ):
                raise ValueError("Unsupported function call history")
            identity = validate_identity(item.get("call_id"))
            if identity in all_ids:
                raise ValueError("Tool call IDs cannot be reused")
            context.validate_arguments(item.get("name"), item.get("arguments"))
            if preserve_assistant_order:
                messages.append({"role": "assistant", "content": None, "tool_calls": []})
            elif not pending:
                if not messages or messages[-1]["role"] != "assistant":
                    messages.append({"role": "assistant", "content": None})
                messages[-1]["tool_calls"] = []
            call = {
                "id": identity,
                "type": "function",
                "function": {"name": item["name"], "arguments": item["arguments"]},
            }
            pending[identity] = item
            all_ids.add(identity)
            messages[-1]["tool_calls"].append(call)
            if len(pending) > profile.max_tools or (
                len(pending) > 1 and "parallel_calls" not in profile.features
            ):
                raise ValueError("Historical parallel calls exceed the profile")
        elif kind == "function_call_output":
            if (
                set(item) - {"type", "id", "call_id", "output", "status"}
                or item.get("status", "completed") != "completed"
            ):
                raise ValueError("Unsupported function result history")
            identity = validate_identity(item.get("call_id"))
            result = item.get("output")
            if (
                identity not in pending
                or not isinstance(result, str)
                or len(result.encode()) > profile.max_result_bytes
            ):
                raise ValueError("Orphan, duplicate or oversized function result")
            pending.pop(identity)
            result_phase = bool(pending)
            messages.append({"role": "tool", "tool_call_id": identity, "content": result})
        elif kind == "message":
            if (
                (pending and (item.get("role") != "assistant" or result_phase))
                or set(item) - {"type", "id", "role", "content", "status"}
                or item.get("status", "completed") != "completed"
            ):
                raise ValueError("Function results must complete before another turn")
            role = item.get("role")
            if role not in {"system", "developer", "user", "assistant"}:
                raise ValueError("Unsupported message role")
            content, count, size = _message_content(
                item.get("content"),
                role,
                profile,
                remaining_images=profile.max_images - image_count,
                remaining_bytes=profile.max_total_image_bytes - image_bytes,
                deadline=deadline,
                image_work=image_work,
            )
            if role in {"system", "developer"} and isinstance(content, list):
                content = "".join(part["text"] for part in content)
            image_count += count
            image_bytes += size
            if image_count > profile.max_images or image_bytes > profile.max_total_image_bytes:
                raise ValueError("Inline images exceed aggregate bounds")
            if pending and not preserve_assistant_order:
                existing = messages[-1].get("content")
                if existing is None:
                    messages[-1]["content"] = content
                else:
                    previous = (
                        [{"type": "text", "text": existing}]
                        if isinstance(existing, str)
                        else existing
                    )
                    current = (
                        [{"type": "text", "text": content}] if isinstance(content, str) else content
                    )
                    messages[-1]["content"] = [*previous, *current]
            else:
                messages.append(
                    {"role": "system" if role == "developer" else role, "content": content}
                )
        else:
            raise ValueError("Unsupported input item")
    if pending:
        raise ValueError("Function history requires a complete result set")
    check_deadline(deadline)
    return messages


def _message_content(
    content: Any,
    role: str,
    profile: GoogleFeatureProfile,
    *,
    remaining_images: int,
    remaining_bytes: int,
    deadline: float | None,
    image_work: ImageWorkBudget,
) -> tuple[Any, int, int]:
    if isinstance(content, str) and content.strip():
        return content, 0, 0
    if not isinstance(content, list) or not 1 <= len(content) <= 64:
        raise ValueError("Message content exceeds its part bound")
    parts: list[dict[str, Any]] = []
    count = size = 0
    for part in content:
        check_deadline(deadline)
        if isinstance(part, str) and part.strip():
            parts.append({"type": "text", "text": part})
        elif isinstance(part, dict) and part.get("type", "input_text") in {
            "text",
            "input_text",
            "output_text",
        }:
            if (
                set(part) - {"type", "text", "annotations"}
                or not isinstance(part.get("text"), str)
                or not part["text"].strip()
                or part.get("annotations", []) != []
            ):
                raise ValueError("Unsupported message text part")
            parts.append({"type": "text", "text": part["text"]})
        elif (
            isinstance(part, dict)
            and part.get("type") == "input_file"
            and role == "user"
            and (
                (
                    "inline_audio" in profile.features
                    and str(part.get("file_data", "")).startswith("data:audio/wav;base64,")
                )
                or (
                    "inline_video" in profile.features
                    and str(part.get("file_data", "")).startswith("data:video/avi;base64,")
                )
                or (
                    "inline_pdfs" in profile.features
                    and str(part.get("file_data", "")).startswith("data:application/pdf;base64,")
                )
            )
        ):
            parts.append({"type": "inline_file", "file_data": part["file_data"]})
        elif (
            isinstance(part, dict)
            and part.get("type") == "input_image"
            and role == "user"
            and "inline_images" in profile.features
        ):
            if count >= remaining_images:
                raise ValueError("Inline images exceed aggregate item bounds")
            uri = part.get("image_url")
            if not isinstance(uri, str) or len(uri) > 24 + 4 * ((remaining_bytes - size + 2) // 3):
                raise ValueError("Inline images exceed aggregate byte bounds")
            size += validate_inline_image(part, profile, deadline=deadline, work_budget=image_work)
            if size > remaining_bytes:
                raise ValueError("Inline images exceed aggregate byte bounds")
            count += 1
            parts.append({"type": "image_url", "image_url": {"url": part["image_url"]}})
        else:
            raise ValueError("Unsupported message content part")
    return parts, count, size


def translate_calls(
    raw_calls: Any, context: GoogleRequestContext, *, completed: bool, refusal: bool = False
) -> list[dict[str, Any]]:
    if not isinstance(raw_calls, list):
        raise ValueError("Provider tool calls must be an array")
    calls: list[dict[str, Any]] = []
    for call in raw_calls:
        if (
            not isinstance(call, dict)
            or set(call) - {"id", "type", "function"}
            or call.get("type") != "function"
        ):
            raise ValueError("Unsupported provider call or continuation state")
        function = call.get("function")
        if not isinstance(function, dict) or set(function) != {"name", "arguments"}:
            raise ValueError("Unsupported provider function or continuation state")
        arguments = function["arguments"]
        if not isinstance(arguments, str) or len(arguments.encode()) > context.max_argument_bytes:
            raise ValueError("Provider function arguments exceed their bound")
        calls.append(
            {
                "type": "function_call",
                "id": f"fc_{uuid.uuid4().hex[:24]}",
                "call_id": call.get("id"),
                "name": function["name"],
                "arguments": arguments,
                "status": "completed" if completed else "incomplete",
            }
        )
    context.validate_calls(calls, completed=completed, refusal=refusal)
    return calls
