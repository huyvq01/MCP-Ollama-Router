"""Local, authenticated chat-completions gateway; no filesystem or shell tools."""
import asyncio
import hmac
import json
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from time import monotonic, time
from typing import Any
from uuid import uuid4

import httpx
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from app.core.logger import configure_logging
from app.dependencies import Container
from app.models.api import CompletionRequest
from app.router.model_size import supported
from app.router.tasks import analyze
from app.runtime import RuntimeSettings, runtime
from app.services.control import BusyError
from app.services.token_budget import estimate_tokens

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"message": message, "type": "router_error", "code": code}}


def tool_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(calls, list):
        raise ValueError("Invalid upstream tool calls")
    result = []
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
            raise ValueError("Invalid upstream tool call")
        function = call.get("function", {})
        if not isinstance(function.get("name"), str) or not function["name"]:
            raise ValueError("Missing upstream function name")
        arguments = function.get("arguments", {})
        if not isinstance(arguments, (str, dict)):
            raise ValueError("Invalid upstream tool arguments")
        result.append({
            "id": call.get("id") or "call_" + uuid4().hex,
            "type": "function",
            "function": {
                "name": function["name"],
                "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
            },
        })
    return result


def usage(data: dict[str, Any]) -> dict[str, int]:
    prompt = data.get("prompt_eval_count", 0)
    completion = data.get("eval_count", 0)
    prompt = prompt if isinstance(prompt, int) and prompt >= 0 else 0
    completion = completion if isinstance(completion, int) and completion >= 0 else 0
    return {"prompt_tokens": prompt, "completion_tokens": completion,
            "total_tokens": prompt + completion}


class ManagedStream(StreamingResponse):
    def __init__(self, content: AsyncIterator[str], stack: AsyncExitStack,
                 headers: dict[str, str]) -> None:
        super().__init__(content, media_type="text/event-stream", headers=headers)
        self._stack = stack

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Covers client disconnects, cancelled streams and failures before
            # the generator starts; never leave an admission slot occupied.
            await self._stack.aclose()


def create_app(container: Container | None = None,
               config: RuntimeSettings = runtime) -> Starlette:
    services = container if container is not None else Container()

    def authorize(request: Request) -> None:
        key = config.gateway_api_key
        if key is None or len(key.get_secret_value()) < 16:
            raise GatewayError(503, "configuration_error", "Gateway API key is not configured.")
        value = request.headers.get("authorization", "")
        expected = "Bearer " + key.get_secret_value()
        if not hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8")):
            raise GatewayError(401, "unauthorized", "A valid bearer API key is required.")

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        if config.gateway_api_key is None or len(config.gateway_api_key.get_secret_value()) < 16:
            raise RuntimeError("Set ROUTER_GATEWAY_API_KEY to at least 16 random characters.")
        try:
            async with asyncio.timeout(config.startup_timeout_s):
                await services.provider_registry.startup()
                await services.registry.refresh()
            yield
        finally:
            await services.provider_registry.shutdown()

    async def live(request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def ready(request: Request) -> Response:
        try:
            authorize(request)
            async with asyncio.timeout(3):
                healthy = await services.provider_registry.healthy()
            available = any(supported(model) for model in services.registry.enabled())
            ok = bool(healthy) and available
            return JSONResponse({"status": "ready" if ok else "not_ready"},
                                status_code=200 if ok else 503)
        except GatewayError as exc:
            return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status)
        except (TimeoutError, httpx.HTTPError):
            return JSONResponse({"status": "not_ready"}, status_code=503)

    async def models(request: Request) -> Response:
        try:
            authorize(request)
            names = ["auto"] + [model.name for model in services.registry.enabled()
                                if supported(model)]
            return JSONResponse({"object": "list", "data": [
                {"id": name, "object": "model", "created": 0, "owned_by": "local-router"}
                for name in names
            ]})
        except GatewayError as exc:
            return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status)

    async def completion(request: Request) -> Response:
        request_id = "chatcmpl-" + uuid4().hex
        headers = {"X-Request-ID": request_id, "Cache-Control": "no-store", "X-Accel-Buffering": "no"}
        deadline = monotonic() + config.request_timeout_s
        stack = AsyncExitStack()
        stream_owned = False
        try:
            authorize(request)
            chunks = bytearray()
            async with asyncio.timeout(config.startup_timeout_s):
                async for chunk in request.stream():
                    chunks.extend(chunk)
                    if len(chunks) > config.max_body_bytes:
                        raise GatewayError(413, "body_too_large", "Request body exceeds the configured limit.")
            body = CompletionRequest.model_validate_json(bytes(chunks))
            prompt = next((item["content"] for item in reversed(body.messages)
                           if item["role"] == "user"), "")
            profile = analyze(prompt)
            output_limit = body.max_tokens or body.max_completion_tokens or min(
                1024 if body.tools else profile.max_tokens, config.max_output_tokens,
            )
            active_tools = body.tools if body.tool_choice != "none" else None
            if body.model == "auto":
                candidates = services.router.selector.rank(prompt, require_tools=bool(active_tools))
            else:
                selected = services.registry.model(body.model)
                if selected is None or not selected.enabled or not supported(selected):
                    raise GatewayError(400, "model_unavailable", "Requested model is not eligible.")
                candidates = [selected]
            if active_tools:
                candidates = [model for model in candidates if "tools" in model.capabilities]
            if not candidates:
                raise GatewayError(503, "no_eligible_model", "No eligible model supports this request.")
            # Preserve client system instructions, history and tool results.
            # Unlike the MCP chat tool, the agent gateway NEVER silently trims input.
            input_estimate = estimate_tokens(json.dumps(
                {"messages": body.messages, "tools": active_tools}, ensure_ascii=False,
            )) + 32
            candidates = [model for model in candidates if input_estimate + output_limit <= (
                min(config.gateway_context_tokens, model.context_length)
                if model.context_length > 0 else config.gateway_context_tokens
            )]
            if not candidates:
                raise GatewayError(400, "context_length_exceeded",
                                   "Input plus output budget exceeds context; reduce files/history or increase context.")
            async with asyncio.timeout(max(0, deadline - monotonic())):
                await stack.enter_async_context(services.router.gate.slot())
            response = None
            chosen = None
            attempts = 0
            for model in candidates:
                key = model.provider + ":" + model.name
                if not services.router.breaker.available(key):
                    continue
                provider = services.provider_registry.get(model.provider)
                if provider is None or model.provider != "ollama":
                    continue
                if attempts >= config.max_attempts:
                    break
                attempts += 1
                client = provider._client()
                options: dict[str, Any] = {
                    "num_ctx": min(config.gateway_context_tokens, model.context_length)
                    if model.context_length > 0 else config.gateway_context_tokens,
                    "num_predict": output_limit,
                    "temperature": body.temperature if body.temperature is not None else profile.temperature,
                }
                for name in ("top_p", "stop", "seed"):
                    value = getattr(body, name)
                    if value is not None:
                        options[name] = [value] if name == "stop" and isinstance(value, str) else value
                payload: dict[str, Any] = {
                    "model": model.name, "messages": body.messages, "options": options,
                    "stream": body.stream, "keep_alive": config.keep_alive,
                }
                if active_tools:
                    payload["tools"] = active_tools
                if "thinking" in model.capabilities:
                    payload["think"] = False
                if body.response_format is not None:
                    payload["format"] = (
                        "json" if body.response_format["type"] == "json_object"
                        else body.response_format["json_schema"]["schema"]
                    )
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise GatewayError(504, "deadline_exceeded", "Request deadline exceeded.")
                try:
                    async with asyncio.timeout(min(remaining, config.attempt_timeout_s)):
                        upstream = client.build_request(
                            "POST", config.ollama_base_url + "/api/chat", json=payload,
                        )
                        response = await client.send(upstream, stream=body.stream)
                        response.raise_for_status()
                    chosen = model
                    break
                except (httpx.HTTPError, TimeoutError) as exc:
                    if response is not None:
                        await response.aclose()
                        response = None
                    if (isinstance(exc, httpx.HTTPStatusError)
                            and exc.response.status_code < 500
                            and exc.response.status_code not in (408, 429)):
                        raise GatewayError(502, "upstream_rejected",
                                           "Ollama rejected the request; check model compatibility.") from exc
                    services.router.breaker.failure(key)
                    logger.warning("gateway_attempt_failed request_id=%s model=%s error_type=%s",
                                   request_id, model.name, type(exc).__name__)
            if response is None or chosen is None:
                raise GatewayError(502, "upstream_unavailable", "Ollama could not complete the request.")
            stack.push_async_callback(response.aclose)
            created = int(time())
            base = {"id": request_id, "created": created, "model": chosen.name}
            key = chosen.provider + ":" + chosen.name
            if not body.stream:
                data = response.json()
                if not isinstance(data, dict) or data.get("error"):
                    raise ValueError("Invalid upstream result")
                message = data.get("message", {})
                if not isinstance(message, dict) or not isinstance(message.get("content", ""), str):
                    raise ValueError("Invalid upstream message")
                calls = tool_calls(message.get("tool_calls", []))
                content = message.get("content", "")
                if not content and not calls:
                    raise ValueError("Empty upstream result")
                output: dict[str, Any] = {"role": "assistant", "content": content or None}
                if calls:
                    output["tool_calls"] = calls
                reason = "tool_calls" if calls else (
                    "length" if data.get("done_reason") == "length" else "stop"
                )
                services.router.breaker.success(key)
                logger.info("gateway_complete request_id=%s model=%s stream=false", request_id, chosen.name)
                return JSONResponse({**base, "object": "chat.completion", "choices": [
                    {"index": 0, "message": output, "finish_reason": reason},
                ], "usage": usage(data)}, headers=headers)

            def event(delta: dict[str, Any], reason: str | None = None) -> str:
                return "data: " + json.dumps({**base, "object": "chat.completion.chunk", "choices": [
                    {"index": 0, "delta": delta, "finish_reason": reason},
                ]}) + "\n\n"

            async def stream() -> AsyncIterator[str]:
                ids: dict[int, str] = {}
                saw_output = False
                done = False
                try:
                    async with asyncio.timeout(max(0, deadline - monotonic())):
                        yield event({"role": "assistant"})
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            data = json.loads(line)
                            if not isinstance(data, dict) or data.get("error"):
                                raise ValueError("Invalid upstream stream")
                            message = data.get("message", {})
                            if not isinstance(message, dict) or not isinstance(message.get("content", ""), str):
                                raise ValueError("Invalid upstream message")
                            content = message.get("content", "")
                            if content:
                                saw_output = True
                                yield event({"content": content})
                            for call in message.get("tool_calls", []):
                                function = call.get("function", {})
                                index = function.get("index", call.get("index", len(ids)))
                                if not isinstance(index, int) or index < 0:
                                    raise ValueError("Invalid upstream tool index")
                                normalized = tool_calls([call])[0]
                                first = index not in ids
                                ids.setdefault(index, normalized["id"])
                                delta: dict[str, Any] = {"index": index, "function": normalized["function"]}
                                if first:
                                    delta.update({"id": ids[index], "type": "function"})
                                saw_output = True
                                yield event({"tool_calls": [delta]})
                            if data.get("done"):
                                if not saw_output:
                                    raise ValueError("Empty upstream stream")
                                reason = "tool_calls" if ids else (
                                    "length" if data.get("done_reason") == "length" else "stop"
                                )
                                yield event({}, reason)
                                if body.stream_options and body.stream_options.get("include_usage"):
                                    yield "data: " + json.dumps({
                                        **base, "object": "chat.completion.chunk", "choices": [], "usage": usage(data),
                                    }) + "\n\n"
                                done = True
                                break
                        if not done:
                            raise ValueError("Upstream stream ended without completion")
                    services.router.breaker.success(key)
                    logger.info("gateway_complete request_id=%s model=%s stream=true", request_id, chosen.name)
                except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
                    services.router.breaker.failure(key)
                    logger.warning("gateway_stream_failed request_id=%s model=%s", request_id, chosen.name)
                    yield "data: " + json.dumps(error_body(
                        "upstream_stream_error", "Stream failed; partial output may be incomplete.",
                    )) + "\n\n"
                finally:
                    await stack.aclose()
                yield "data: [DONE]\n\n"

            result = ManagedStream(stream(), stack, headers)
            stream_owned = True
            return result
        except GatewayError as exc:
            return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status, headers=headers)
        except ValidationError:
            return JSONResponse(error_body("invalid_request", "Invalid fields, messages or generation limits."),
                                status_code=400, headers=headers)
        except BusyError:
            return JSONResponse(error_body("router_busy", "Router is busy; retry later."),
                                status_code=429, headers={**headers, "Retry-After": "5"})
        except (TimeoutError, httpx.TimeoutException):
            return JSONResponse(error_body("deadline_exceeded", "Request deadline exceeded."),
                                status_code=504, headers=headers)
        except (ValueError, KeyError, TypeError, httpx.HTTPError):
            if "key" in locals():
                services.router.breaker.failure(key)
            logger.warning("gateway_protocol_error request_id=%s", request_id)
            return JSONResponse(error_body("upstream_error", "Invalid response from Ollama."),
                                status_code=502, headers=headers)
        finally:
            # Streaming owns the stack until its response finishes.
            if not stream_owned:
                await stack.aclose()

    return Starlette(routes=[
        Route("/health/live", live), Route("/health/ready", ready),
        Route("/v1/models", models), Route("/v1/chat/completions", completion, methods=["POST"]),
    ], lifespan=lifespan)


app = create_app()

if __name__ == "__main__":
    import uvicorn

    configure_logging()
    uvicorn.run("app.gateway:app", host=runtime.gateway_host, port=runtime.gateway_port,
                workers=1, log_config=None, access_log=False)
