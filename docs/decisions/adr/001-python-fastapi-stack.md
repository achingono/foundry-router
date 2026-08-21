# ADR-001: Python 3.12+, FastAPI, and Async Stack

## Status
Accepted

## Context
The Foundry Router must be a lightweight, asynchronous HTTP proxy suitable for Azure Container Apps scale-to-zero deployment. Key requirements:
- Asynchronous request handling for streaming and high concurrency
- OpenAPI/Swagger documentation generation
- Type safety with modern Python tooling
- Small memory footprint for Consumption plan (0.5 GiB)
- Fast cold start for scale-to-zero

## Decision
We will use:
- **Python 3.12+** for modern async support, performance improvements, and long-term support
- **FastAPI** for automatic OpenAPI generation, dependency injection, and async-first design
- **httpx** for async HTTP client with streaming support
- **Pydantic v2** for configuration validation and request/response modeling
- **structlog** for structured JSON logging with contextvars
- **uvicorn** as ASGI server

## Consequences

### Positive
- Native async/await for streaming pass-through without blocking
- Automatic API documentation at `/docs` and `/redoc`
- Excellent type hint support with mypy/pyright
- Small dependency footprint compared to frameworks like Starlette + extras
- Strong ecosystem for testing (pytest-asyncio, httpx-mock)

### Negative
- Python GIL limits CPU-bound parallelism (not an issue for I/O-bound proxy)
- Cold start slower than Go/Rust but acceptable for Container Apps Consumption
- Requires Python runtime in container (mitigated by slim base image)

### Neutral
- Team must be proficient in async Python patterns
- Structured logging requires structlog-specific patterns

## Alternatives Considered
- **Go + Gin/Echo**: Faster cold start, smaller binary, but less mature async streaming ecosystem and no automatic OpenAPI
- **Node.js + Fastify**: Good async, but dynamic typing adds risk for config validation
- **Rust + Axum**: Best performance, but steep learning curve and slower development velocity
- **Starlette (raw)**: More control but more boilerplate; FastAPI adds minimal overhead

## Related
- ADR-002: Configuration with Pydantic Settings
- ADR-003: Structured Logging with structlog

## References
- FastAPI documentation: https://fastapi.tiangolo.com/
- Azure Container Apps Python guide: https://learn.microsoft.com/azure/container-apps/quickstart-python