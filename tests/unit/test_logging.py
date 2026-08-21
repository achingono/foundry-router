"""Unit tests for logging module."""

from __future__ import annotations

import json
import re

from foundry_router.logging import (
    SENSITIVE_FIELDS,
    SENSITIVE_PATTERNS,
    get_logger,
    redact_dict,
    redact_processor,
    setup_logging,
)


class TestRedactDict:
    def test_redacts_sensitive_keys(self) -> None:
        data = {"api_key": "secret123", "normal_field": "value"}
        result = redact_dict(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["normal_field"] == "value"

    def test_redacts_nested_sensitive_keys(self) -> None:
        data = {"outer": {"authorization": "Bearer token123", "safe": "ok"}}
        result = redact_dict(data)
        assert result["outer"]["authorization"] == "[REDACTED]"
        assert result["outer"]["safe"] == "ok"

    def test_redacts_list_of_dicts(self) -> None:
        data = {"items": [{"secret": "value1"}, {"public": "value2"}]}
        result = redact_dict(data)
        assert result["items"][0]["secret"] == "[REDACTED]"
        assert result["items"][1]["public"] == "value2"

    def test_redacts_patterns_in_strings(self) -> None:
        data = {"message": "Authorization: Bearer abc123"}
        result = redact_dict(data)
        assert "[REDACTED]" in result["message"]
        assert "abc123" not in result["message"]

    def test_redacts_jwt_pattern(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        data = {"token": jwt}
        result = redact_dict(data)
        assert result["token"] == "[REDACTED]"

    def test_preserves_non_sensitive_data(self) -> None:
        data = {
            "request_id": "req-123",
            "model": "gpt-4",
            "latency_ms": 150,
            "tokens_in": 100,
            "tokens_out": 50,
            "estimated_cost_usd": 0.001,
        }
        result = redact_dict(data)
        assert result == data


class TestRedactProcessor:
    def test_processor_redacts_event_dict(self) -> None:
        event_dict = {
            "event": "request_completed",
            "api_key": "secret",
            "model": "gpt-4",
        }
        result = redact_processor(None, "info", event_dict)
        assert result["api_key"] == "[REDACTED]"
        assert result["model"] == "gpt-4"
        assert result["event"] == "request_completed"


class TestSetupLogging:
    def test_setup_logging_configures_structlog(self, capsys) -> None:
        setup_logging("INFO")

        logger = get_logger("test")
        logger.info("test_message", model="gpt-4", latency_ms=100)

        captured = capsys.readouterr()
        log_entry = json.loads(captured.out.strip())

        assert log_entry["event"] == "test_message"
        assert log_entry["model"] == "gpt-4"
        assert log_entry["latency_ms"] == 100
        assert "timestamp" in log_entry
        assert log_entry["level"] == "info"

    def test_log_level_respected(self, capsys) -> None:
        setup_logging("WARNING")

        logger = get_logger("test")
        logger.info("should not appear")
        logger.warning("should appear")

        captured = capsys.readouterr()
        output = captured.out
        assert "should not appear" not in output
        assert "should appear" in output


class TestSensitiveFields:
    def test_sensitive_fields_comprehensive(self) -> None:
        # Ensure all expected sensitive fields are covered
        expected = {
            "authorization",
            "api_key",
            "api-key",
            "x-api-key",
            "apikey",
            "credential",
            "password",
            "secret",
            "token",
            "access_token",
            "refresh_token",
            "prompt",
            "completion",
            "response",
            "output",
            "text",
            "content",
            "message",
            "choices",
            "embeddings",
            "data",
        }
        assert expected == SENSITIVE_FIELDS


class TestSensitivePatterns:
    def test_patterns_compile(self) -> None:
        for pattern in SENSITIVE_PATTERNS:
            assert isinstance(pattern, re.Pattern)

    def test_bearer_token_pattern(self) -> None:
        pattern = SENSITIVE_PATTERNS[0]
        assert pattern.search("Authorization: Bearer abc123")
        assert pattern.search("bearer xyz789")
        assert not pattern.search("Bearer")

    def test_api_key_pattern(self) -> None:
        pattern = SENSITIVE_PATTERNS[1]
        assert pattern.search("api_key: secret123")
        assert pattern.search("api-key=secret123")
        assert not pattern.search("api_key:")

    def test_sk_pattern(self) -> None:
        pattern = SENSITIVE_PATTERNS[2]
        assert pattern.search("sk-abcdefghijklmnopqrstuvwxyz123456")
        assert not pattern.search("sk-short")
