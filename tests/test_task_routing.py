from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.config import MAX_CONTEXT_TOKENS
from app.models.chat import ChatRequest, ChatResult
from app.prompts.message import MessageBuilder
from app.registry.schemas import ModelMetadata
from app.router.engine import RouterEngine
from app.router.matcher import Capability, matcher
from app.router.selector import ModelSelector
from app.router.tasks import Task, analyze
from app.services.history import HistoryManager
from app.services.token_budget import estimate_message_tokens


def registry_for_machine():
    registry = Mock()
    registry.enabled.return_value = [
        ModelMetadata(
            provider="ollama", name="deepseek-r1:8b", parameter_size="8.2B",
            capabilities=["general", "reasoning"], priority=80,
        ),
        ModelMetadata(
            provider="ollama", name="qwen2.5-coder:7b", parameter_size="7.6B",
            capabilities=["general", "code"], priority=100,
        ),
        ModelMetadata(
            provider="ollama", name="gemma3:4b", parameter_size="4.3B",
            capabilities=["general"], priority=100,
        ),
    ]
    return registry


@pytest.mark.parametrize(
    ("prompt", "task", "model"),
    [
        ("Viết code Java tạo REST API", Task.CODE, "qwen2.5-coder:7b"),
        ("Sửa lỗi đoạn mã này", Task.CODE, "qwen2.5-coder:7b"),
        ("Write a Python function to sort records", Task.CODE, "qwen2.5-coder:7b"),
        ("Viết code đọc file README", Task.CODE, "qwen2.5-coder:7b"),
        ("Hãy viết code đọc file README", Task.CODE, "qwen2.5-coder:7b"),
        ("Please write a Python function to read README", Task.CODE, "qwen2.5-coder:7b"),
        ("Viết tài liệu API Spring Boot", Task.DOCUMENTATION, "gemma3:4b"),
        ("Write README for the Python API", Task.DOCUMENTATION, "gemma3:4b"),
        ("Java là gì?", Task.EXPLAIN, "gemma3:4b"),
        ("Giai thich dependency injection", Task.EXPLAIN, "gemma3:4b"),
        ("Explain this code: ```python\nprint(1)\n```", Task.EXPLAIN, "gemma3:4b"),
        ("So sánh interface và abstract class", Task.EXPLAIN, "gemma3:4b"),
        ("Xin chào", Task.GENERAL, "gemma3:4b"),
    ],
)
@pytest.mark.asyncio
async def test_routes_tasks_on_current_machine(prompt, task, model):
    assert analyze(prompt).task == task
    selector = ModelSelector(registry_for_machine())
    assert (await selector.select(prompt)).name == model


def test_word_boundaries_avoid_false_code_detection():
    assert matcher.match("google logo") == Capability.GENERAL
    assert matcher.match("write Go code") == Capability.CODE


def test_followup_inherits_task_but_new_topic_does_not():
    history = [{"role": "user", "content": "Viết tài liệu API Spring Boot"}]
    assert analyze("Viết tiếp phần cài đặt", history).task == Task.DOCUMENTATION
    assert analyze("Java là gì?", history).task == Task.EXPLAIN
    assert analyze("Xin chào", history).task == Task.GENERAL
    history += [
        {"role": "assistant", "content": "# Documentation"},
        {"role": "user", "content": "Viết tiếp phần cài đặt"},
    ]
    assert analyze("Tiếp tục", history).task == Task.DOCUMENTATION


def test_budgets_follow_task_and_detail_request():
    assert analyze("Xin chào").max_tokens == 192
    assert analyze("Java là gì?").max_tokens == 384
    assert analyze("Viết code Java").max_tokens == 768
    assert analyze("Viết README").max_tokens == 1024
    assert analyze("Viết tài liệu chi tiết").max_tokens == 1536
    assert analyze("Viết tài liệu ngắn gọn").max_tokens == 256


@pytest.mark.parametrize("budget", [192, 768, 1024, 1536, 2048])
def test_dynamic_output_budget_reserves_context(budget):
    profile = analyze("Viết tài liệu API")
    messages = MessageBuilder().build(
        [{"role": "user", "content": "old history " * 2000}],
        "prompt " * 4000,
        instruction=profile.instruction,
        output_tokens=budget,
    )
    assert sum(estimate_message_tokens(message) for message in messages) <= (
        MAX_CONTEXT_TOKENS - budget
    )
    assert profile.instruction in messages[0]["content"]


@pytest.mark.parametrize("budget", [0, -1, 2049])
def test_invalid_generation_limits_are_rejected(budget):
    with pytest.raises(ValidationError):
        ChatRequest(model="test", messages=[], max_tokens=budget)


@pytest.mark.asyncio
async def test_engine_applies_task_settings_and_explicit_override():
    registry = registry_for_machine()
    provider = Mock()
    provider.chat = AsyncMock(return_value=ChatResult(
        provider="ollama", model="gemma3:4b", content="# API\nUsage instructions",
    ))
    providers = Mock()
    providers.get.return_value = provider
    router = RouterEngine(providers, registry, HistoryManager())

    await router.chat("docs", "Viết tài liệu API")
    request = provider.chat.await_args.args[0]
    assert request.model == "gemma3:4b"
    assert request.max_tokens == 1024
    assert request.temperature == 0.4
    assert "Markdown documentation" in request.messages[0]["content"]
    await router.chat("docs", "Viết tiếp phần cài đặt", max_tokens=160)
    request = provider.chat.await_args.args[0]
    assert request.max_tokens == 160
    assert "Markdown documentation" in request.messages[0]["content"]


@pytest.mark.asyncio
async def test_fallback_keeps_code_specialists_first():
    registry = registry_for_machine()
    selected = registry.enabled.return_value[1]
    backup = ModelMetadata(
        provider="ollama", name="coder:3b", parameter_size="3B",
        capabilities=["code", "general"], priority=120,
    )
    registry.enabled.return_value.append(backup)
    registry.model.return_value = selected
    provider = Mock()
    provider.chat = AsyncMock(side_effect=[
        RuntimeError("primary unavailable"),
        ChatResult(provider="ollama", model=backup.name, content="print(1)"),
    ])
    providers = Mock()
    providers.get.return_value = provider
    router = RouterEngine(providers, registry, HistoryManager())

    assert await router.chat("code", "Viết code Python", model=selected.name)
    assert [call.args[0].model for call in provider.chat.await_args_list] == [
        selected.name, backup.name,
    ]


@pytest.mark.asyncio
async def test_selector_rejects_only_oversized_models():
    registry = registry_for_machine()
    registry.enabled.return_value = registry.enabled.return_value[:1]
    with pytest.raises(RuntimeError, match="size limit"):
        await ModelSelector(registry).select("Viết code")


def test_preview_uses_same_route_without_inference(monkeypatch):
    from app.tools import router as router_tools

    registry = registry_for_machine()
    providers = Mock()
    history = HistoryManager()
    router = RouterEngine(providers, registry, history)
    monkeypatch.setattr(router_tools.container, "router", router)
    monkeypatch.setattr(router_tools.container, "registry", registry)
    monkeypatch.setattr(router_tools.container, "history", history)
    functions = {}
    server = Mock()
    server.tool.side_effect = lambda function: functions.setdefault(
        function.__name__, function,
    )
    router_tools.register(server)
    preview = functions["route_preview"]("Viết tài liệu API")
    assert preview["task"] == "documentation"
    assert preview["selected_model"] == "gemma3:4b"
    assert preview["max_tokens"] == 1024
    assert preview["excluded_models"] == ["deepseek-r1:8b"]
    assert providers.mock_calls == []
