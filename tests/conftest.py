import os

import pytest_asyncio

# Unit tests must not inherit the operator's .env context/hardware policy.
for _name, _value in {
    "ROUTER_ALLOW_UNKNOWN_MODEL_SIZE": "true",
    "ROUTER_CONTEXT_TOKENS": "4096",
    "ROUTER_GATEWAY_CONTEXT_TOKENS": "4096",
    "ROUTER_MAX_OUTPUT_TOKENS": "2048",
    "ROUTER_PROMPT_TOKENS": "2048",
    "ROUTER_MAX_MODEL_BILLIONS": "8",
    "ROUTER_MAX_CONCURRENT": "1",
    "ROUTER_MAX_PENDING": "8",
    "ROUTER_REQUEST_TIMEOUT_S": "90",
    "ROUTER_ATTEMPT_TIMEOUT_S": "45",
    "ROUTER_QUEUE_TIMEOUT_S": "5",
    "ROUTER_HISTORY_MESSAGES": "6",
    "ROUTER_HISTORY_TOKENS": "1536",
    "ROUTER_MAX_SESSIONS": "256",
    "ROUTER_SESSION_TTL_S": "3600",
    "ROUTER_MAX_BODY_BYTES": "262144",
}.items():
    os.environ[_name] = _value

from app.dependencies import container


@pytest_asyncio.fixture
async def provider_registry():
    registry = container.provider_registry

    await registry.startup()

    try:
        yield registry
    finally:
        await registry.shutdown()


@pytest_asyncio.fixture
async def registry(provider_registry):
    await container.registry.refresh()
    return container.registry


@pytest_asyncio.fixture
def router():
    return container.router


@pytest_asyncio.fixture
def history():
    return container.history


@pytest_asyncio.fixture
def cache():
    return container.cache


@pytest_asyncio.fixture
def session():
    return container.session
