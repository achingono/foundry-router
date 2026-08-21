# Phase 03 Evidence

## Evidence Log

| Item | Reference | Notes |
|---|---|---|
| Plan review | Independent review completed | Protocol, health states, retry/cooldown, failover, streaming contract, and test scope resolved before implementation |
| Focused tests | `PYTHONPATH=src uv run --python 3.12 --no-project --with pytest --with pytest-asyncio --with respx --with fastapi==0.110.0 --with httpx==0.27.2 --with pydantic==2.11.7 --with pydantic-settings --with structlog --with uvicorn python -m pytest tests/unit/test_main.py -q` | 45 passed; includes safe response headers, retry timing, three-backend exclusion, same-backend state races, status-body cleanup, cancellation cleanup, and bounded pre-output streaming |
| Full unit verification | `PYTHONPATH=src uv run --python 3.12 --no-project --with pytest --with pytest-asyncio --with pytest-cov --with respx --with fastapi==0.110.0 --with httpx==0.27.2 --with pydantic==2.11.7 --with pydantic-settings --with structlog --with uvicorn python -m pytest tests/unit -q --cov=src/foundry_router --cov-report=term-missing` | 104 passed; 87.60% total coverage |
| Lint verification | `PYTHONPATH=src uv run --python 3.12 --no-project --with ruff ruff check src/foundry_router tests/unit` | Passed |
| Formatting verification | `PYTHONPATH=src uv run --python 3.12 --no-project --with ruff ruff format --check src/foundry_router tests/unit` | Passed |
| Type verification | `PYTHONPATH=src uv run --python 3.12 --no-project --with mypy --with fastapi==0.110.0 --with httpx==0.27.2 --with pydantic==2.11.7 --with pydantic-settings --with structlog --with uvicorn mypy src/` | Strict mypy passed |
| Container verification | `docker build -t foundry-router:phase-03-hardening .` | Passed |
| Documentation review | README and canonical docs listed in exit criteria | Status and traceability updated; credit/metrics/infrastructure remain Planned |
