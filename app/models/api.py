"""The documented chat-completions subset accepted by the local gateway."""
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import MAX_REQUEST_OUTPUT_TOKENS


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(default="auto", min_length=1, max_length=256)
    messages: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    stream: bool = False
    stream_options: dict[str, bool] | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=MAX_REQUEST_OUTPUT_TOKENS)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=MAX_REQUEST_OUTPUT_TOKENS)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    stop: str | list[str] | None = None
    seed: int | None = None
    tools: list[dict[str, Any]] | None = Field(default=None, max_length=128)
    tool_choice: Literal["auto", "none"] | None = None
    parallel_tool_calls: bool | None = None
    response_format: dict[str, Any] | None = None
    n: Literal[1] = 1
    user: str | None = Field(default=None, max_length=128)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        names: dict[str, str] = {}
        result = []
        for source in messages:
            message = dict(source)
            role = message.get("role")
            if role not in {"system", "developer", "user", "assistant", "tool"}:
                raise ValueError("Unsupported message role")
            content = message.get("content")
            if isinstance(content, list):
                if any(not isinstance(part, dict) or part.get("type") != "text"
                       or not isinstance(part.get("text"), str) for part in content):
                    raise ValueError("Only text content blocks are supported")
                content = "\n".join(part["text"] for part in content)
            if content is not None and not isinstance(content, str):
                raise ValueError("Message content must be text")
            normalized: dict[str, Any] = {
                "role": "system" if role == "developer" else role,
                "content": content or "",
            }
            calls = message.get("tool_calls")
            if calls:
                if role != "assistant" or not isinstance(calls, list):
                    raise ValueError("tool_calls are only accepted in assistant messages")
                normalized["tool_calls"] = []
                for call in calls:
                    if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                        raise ValueError("Invalid tool call")
                    function = dict(call["function"])
                    name = function.get("name")
                    if not isinstance(name, str) or not name:
                        raise ValueError("Tool call requires a function name")
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError as exc:
                            raise ValueError("Tool arguments must be JSON") from exc
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be an object")
                    normalized["tool_calls"].append({
                        "function": {"name": name, "arguments": arguments},
                    })
                    if isinstance(call.get("id"), str):
                        names[call["id"]] = name
            if role == "tool":
                name = names.get(message.get("tool_call_id", "")) or message.get("name")
                if not isinstance(name, str) or not name:
                    raise ValueError("Tool response must reference a preceding tool call")
                normalized["tool_name"] = name
            result.append(normalized)
        return result

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        for tool in tools or []:
            function = tool.get("function")
            if tool.get("type") != "function" or not isinstance(function, dict):
                raise ValueError("Only function tools are supported")
            if not isinstance(function.get("name"), str) or not function["name"]:
                raise ValueError("Function tools require a name")
            if not isinstance(function.get("parameters", {}), dict):
                raise ValueError("Function parameters must be a JSON schema object")
        return tools

    @model_validator(mode="after")
    def validate_options(self) -> "CompletionRequest":
        if self.max_tokens is not None and self.max_completion_tokens is not None:
            raise ValueError("Specify only one output token limit")
        if self.stream_options and set(self.stream_options) != {"include_usage"}:
            raise ValueError("Unsupported stream option")
        if self.parallel_tool_calls is False:
            raise ValueError("Forced sequential tool calls are not supported by this gateway")
        if self.response_format is not None:
            kind = self.response_format.get("type")
            schema = self.response_format.get("json_schema", {})
            if kind != "json_object" and not (
                kind == "json_schema" and isinstance(schema, dict)
                and isinstance(schema.get("schema"), dict)
            ):
                raise ValueError("Unsupported response_format")
        if isinstance(self.stop, list) and (
            len(self.stop) > 16 or any(len(item) > 256 for item in self.stop)
        ):
            raise ValueError("Stop sequences exceed the limit")
        return self
