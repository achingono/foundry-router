"""Strict, bounded HTTP/1.1 ingress and fixed-origin TLS helpers."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ssl
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import h11

from .errors import AuthorizationError, ProtocolError

if TYPE_CHECKING:
    from asyncio import StreamReader, StreamWriter

MAX_HEADER_BYTES = 32_768
READ_CHUNK_BYTES = 16_384
MAX_READ_TIMEOUT_SECONDS = 10.0
MAX_REQUEST_BYTES = 1_048_576
SHA256_HEX_LENGTH = 64
MIN_HTTP_HEADER_LINES = 2
ORIGIN_PORT = 443
HEALTH_ROUTE = (b"GET", b"/health/ready")
RESPONSES_ROUTE = (b"POST", b"/openai/v1/responses")
ADMIN_ROUTE = (b"GET", b"/admin/status")
ALLOWED_HEADERS = frozenset(
    {
        b"host",
        b"content-length",
        b"content-type",
        b"connection",
        b"authorization",
        b"api-key",
        b"x-admin-key",
    }
)


@dataclass(frozen=True, slots=True)
class IngressRequest:
    method: bytes
    target: bytes
    headers: tuple[tuple[bytes, bytes], ...] = field(repr=False)
    body: bytes = field(repr=False)


def _header_map(request: h11.Request) -> dict[bytes, bytes]:
    headers: dict[bytes, bytes] = {}
    for raw_name, raw_value in request.headers:
        name = raw_name.lower()
        if name in headers:
            raise ProtocolError("duplicate HTTP headers are not permitted")
        if name not in ALLOWED_HEADERS:
            raise ProtocolError("HTTP header is not permitted")
        headers[name] = raw_value.strip()
    return headers


def _validate_common_headers(headers: dict[bytes, bytes], *, origin_host: str) -> None:
    if headers.get(b"host") not in {
        origin_host.encode("ascii"),
        f"{origin_host}:443".encode("ascii"),
    }:
        raise ProtocolError("HTTP Host does not match the packet-bound origin")
    if headers.get(b"connection", b"close").lower() != b"close":
        raise ProtocolError("ingress connections must close after one request")


def _canonical_content_length(value: bytes) -> int:
    if not value.isdigit() or (len(value) > 1 and value.startswith(b"0")):
        raise ProtocolError("Content-Length is invalid")
    return int(value)


def _reject_duplicate_wire_headers(header_block: bytes) -> None:
    lines = header_block.split(b"\r\n")
    if len(lines) < MIN_HTTP_HEADER_LINES:
        raise ProtocolError("HTTP request headers are missing")
    seen: set[bytes] = set()
    for line in lines[1:]:
        if line.startswith((b" ", b"\t")) or b":" not in line:
            raise ProtocolError("obsolete or malformed HTTP header line")
        name = line.partition(b":")[0].lower()
        if not name or name in seen:
            raise ProtocolError("duplicate or empty HTTP header name")
        seen.add(name)


def _request_body_length(
    method: bytes,
    headers: dict[bytes, bytes],
    *,
    max_request_bytes: int,
) -> int:
    if method == b"POST":
        length_text = headers.get(b"content-length")
        if length_text is None:
            raise ProtocolError("POST requires a canonical Content-Length")
        content_length = _canonical_content_length(length_text)
        if content_length > max_request_bytes:
            raise ProtocolError("request body exceeds the packet limit")
        if headers.get(b"content-type") != b"application/json":
            raise ProtocolError("POST Content-Type must be application/json")
        return content_length

    content_length = _canonical_content_length(headers.get(b"content-length", b"0"))
    if content_length != 0:
        raise ProtocolError("health requests cannot have a body")
    if b"content-type" in headers:
        raise ProtocolError("health requests cannot specify a Content-Type")
    return content_length


def _validate_request_head(
    request: h11.Request,
    *,
    origin_host: str,
    max_request_bytes: int,
    peer_role: Literal["runner", "verifier"],
    forwarding_open: bool,
) -> tuple[dict[bytes, bytes], int]:
    if not origin_host.isascii() or origin_host != origin_host.lower():
        raise ProtocolError("configured origin host is invalid")
    if not 0 < max_request_bytes <= MAX_REQUEST_BYTES:
        raise ProtocolError("request size limit is invalid")
    if not forwarding_open or peer_role not in {"runner", "verifier"}:
        raise AuthorizationError("normal forwarding is closed or identity is invalid")
    route = (request.method, request.target)
    if route not in {HEALTH_ROUTE, RESPONSES_ROUTE, ADMIN_ROUTE}:
        raise ProtocolError("HTTP method or route is not permitted")
    if (route == RESPONSES_ROUTE and peer_role != "runner") or (
        route == ADMIN_ROUTE and peer_role != "verifier"
    ):
        raise AuthorizationError("authenticated identity is not permitted on this route")
    if request.http_version != b"1.1":
        raise ProtocolError("only HTTP/1.1 is permitted")
    if b"?" in request.target or b"#" in request.target:
        raise ProtocolError("query strings and fragments are not permitted")

    headers = _header_map(request)
    _validate_common_headers(headers, origin_host=origin_host)
    credentials = set(headers) & {b"authorization", b"api-key", b"x-admin-key"}
    if route == HEALTH_ROUTE:
        if credentials:
            raise AuthorizationError("credentials are not accepted on readiness")
    else:
        allowed = {b"authorization", b"api-key" if route == RESPONSES_ROUTE else b"x-admin-key"}
        if len(credentials) != 1 or not credentials <= allowed:
            raise AuthorizationError("one route-specific credential is required")
        name = next(iter(credentials))
        value = headers[name]
        if not value or (name == b"authorization" and not value.startswith(b"Bearer ")):
            raise AuthorizationError("route credential is invalid")
        if name == b"authorization" and not value[len(b"Bearer ") :].strip():
            raise AuthorizationError("route credential is invalid")
    content_length = _request_body_length(
        request.method,
        headers,
        max_request_bytes=max_request_bytes,
    )
    return headers, content_length


# This event loop explicitly rejects every parser event outside the one-request protocol.
async def read_ingress_request(  # noqa: PLR0913 -- each bound is independently enforced
    reader: StreamReader,
    *,
    origin_host: str,
    max_request_bytes: int,
    peer_role: Literal["runner", "verifier"],
    forwarding_open: bool,
    timeout_seconds: float = MAX_READ_TIMEOUT_SECONDS,
) -> IngressRequest:
    """Read exactly one bounded request; unsupported or ambiguous framing fails closed."""
    if not 0 < timeout_seconds <= MAX_READ_TIMEOUT_SECONDS:
        raise ProtocolError("request read timeout is outside the approved bound")
    parser = h11.Connection(
        h11.SERVER,
        max_incomplete_event_size=MAX_HEADER_BYTES,
    )
    request: h11.Request | None = None
    headers: dict[bytes, bytes] | None = None
    expected_body_length: int | None = None
    body = bytearray()
    header_capture = bytearray()
    headers_checked = False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds

    while True:
        try:
            event = parser.next_event()
        except h11.RemoteProtocolError as exc:
            raise ProtocolError("malformed HTTP request") from exc
        if event is h11.NEED_DATA:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise ProtocolError("request read timed out")
            try:
                data = await asyncio.wait_for(
                    reader.read(READ_CHUNK_BYTES),
                    timeout=remaining,
                )
            except TimeoutError as exc:
                raise ProtocolError("request read timed out") from exc
            if not headers_checked:
                header_capture.extend(data)
                delimiter = header_capture.find(b"\r\n\r\n")
                if delimiter >= 0:
                    if delimiter > MAX_HEADER_BYTES:
                        raise ProtocolError("HTTP headers exceed the configured limit")
                    _reject_duplicate_wire_headers(bytes(header_capture[:delimiter]))
                    headers_checked = True
                elif len(header_capture) > MAX_HEADER_BYTES:
                    raise ProtocolError("HTTP headers exceed the configured limit")
            try:
                parser.receive_data(data)
            except h11.RemoteProtocolError as exc:
                raise ProtocolError("malformed HTTP request") from exc
            continue
        if isinstance(event, h11.Request):
            if request is not None:
                raise ProtocolError("only one request is permitted per connection")
            request = event
            headers, expected_body_length = _validate_request_head(
                event,
                origin_host=origin_host,
                max_request_bytes=max_request_bytes,
                peer_role=peer_role,
                forwarding_open=forwarding_open,
            )
        elif isinstance(event, h11.Data):
            if request is None or expected_body_length is None:
                raise ProtocolError("HTTP body arrived before a valid request")
            body.extend(event.data)
            if len(body) > expected_body_length or len(body) > max_request_bytes:
                raise ProtocolError("HTTP body exceeds its declared or packet limit")
        elif isinstance(event, h11.EndOfMessage):
            if request is None or headers is None or expected_body_length is None:
                raise ProtocolError("HTTP request ended before its headers")
            if len(body) != expected_body_length:
                raise ProtocolError("HTTP body length does not match Content-Length")
            trailing_data, _ = parser.trailing_data
            if trailing_data:
                raise ProtocolError("HTTP pipelining is not permitted")
            return IngressRequest(
                method=request.method,
                target=request.target,
                headers=tuple(sorted(headers.items())),
                body=bytes(body),
            )
        elif event is h11.PAUSED:
            raise ProtocolError("HTTP pipelining is not permitted")
        elif isinstance(event, h11.ConnectionClosed):
            raise ProtocolError("connection closed before request completion")
        else:
            raise ProtocolError("unexpected HTTP parser event")


def verify_tls_peer(
    writer: StreamWriter,
    *,
    expected_certificate_sha256: str,
) -> None:
    """Require the peer's leaf certificate to match the packet-bound fingerprint."""
    if len(expected_certificate_sha256) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in expected_certificate_sha256
    ):
        raise ProtocolError("expected TLS certificate fingerprint is invalid")
    ssl_object = writer.get_extra_info("ssl_object")
    if not isinstance(ssl_object, ssl.SSLObject):
        raise AuthorizationError("connection is not protected by TLS")
    certificate = ssl_object.getpeercert(binary_form=True)
    if not certificate:
        raise AuthorizationError("TLS peer did not present a certificate")
    actual = hashlib.sha256(certificate).hexdigest()
    if not hmac.compare_digest(actual, expected_certificate_sha256):
        raise AuthorizationError("TLS peer certificate does not match the packet")


def create_ingress_server_context(
    *,
    certificate_file: str,
    private_key_file: str,
    client_ca_file: str,
) -> ssl.SSLContext:
    """Create a TLS 1.2+ server context that requires client certificates."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION
    context.load_cert_chain(certificate_file, private_key_file)
    context.load_verify_locations(cafile=client_ca_file)
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def create_origin_client_context(
    *,
    origin_ca_file: str,
    client_certificate_file: str,
    client_private_key_file: str,
) -> ssl.SSLContext:
    """Create a TLS client context with explicit trust and client identity."""
    context = ssl.create_default_context(cafile=origin_ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION
    context.load_cert_chain(client_certificate_file, client_private_key_file)
    return context


async def open_fixed_origin(
    origin_host: str,
    *,
    ssl_context: ssl.SSLContext,
    expected_certificate_sha256: str,
    timeout_seconds: float = MAX_READ_TIMEOUT_SECONDS,
) -> tuple[StreamReader, StreamWriter]:
    """Open one direct TLS connection to the fixed port-443 packet origin."""
    if (
        not origin_host.isascii()
        or origin_host != origin_host.lower()
        or not 0 < timeout_seconds <= MAX_READ_TIMEOUT_SECONDS
        or ssl_context.verify_mode != ssl.CERT_REQUIRED
        or not ssl_context.check_hostname
    ):
        raise ProtocolError("fixed-origin TLS configuration is not secure")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                origin_host,
                ORIGIN_PORT,
                ssl=ssl_context,
                server_hostname=origin_host,
            ),
            timeout=timeout_seconds,
        )
    except (OSError, ssl.SSLError, TimeoutError) as exc:
        raise AuthorizationError("fixed-origin TLS connection failed") from exc
    try:
        verify_tls_peer(
            writer,
            expected_certificate_sha256=expected_certificate_sha256,
        )
    except (AuthorizationError, ProtocolError):
        writer.close()
        raise
    return reader, writer
