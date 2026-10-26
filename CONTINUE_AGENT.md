# Continue + Ollama agent bridge

Continue uses the local OpenAI-compatible API at http://127.0.0.1:18080/v1.
The bridge forwards to Ollama at http://127.0.0.1:11434. It repairs complete
JSON function calls returned as text only if the function was advertised and
the arguments satisfy its JSON schema. It never executes a tool itself.
Native tool calls are preserved. Examples embedded in prose, unknown calls,
invalid arguments, truncated generations and disabled tool calls are not promoted.

## Start after restarting the computer

Open PowerShell in this repository and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_agent_bridge.ps1
```

Keep that terminal open. Start Ollama as well. Then reload VS Code, select
Continue's local configuration `Ollama Local Agent`, model
`Qwen Coder 3B Agent Bridge`, and Agent mode. Start a new conversation.

Try: `Dung read_file doc app/server.py, sau do giai thich ham create_server.`
Check for an actual tool execution card, not just JSON text.

The project MCP configuration runs `python -m app.server --coding-tools`.
This optional profile advertises eight tools: workspace_info, list_files,
read_file, search_code, propose_changes, apply_changes, run_check and
rollback_changes. Without the flag all existing tools remain available.
The Cline MCP connection was disabled so that Continue can own this workspace.
Do not enable both clients for the same workspace at once.

The bridge buffers the Ollama response before emitting OpenAI SSE events.
Tokens therefore appear after generation rather than immediately. It listens
only on loopback and is intended for local desktop use. It does not add
automatic model routing or guarantee the model will choose the right tool.
Continue still handles tool execution and approval. Review changes as usual.

## Validation

```powershell
.\.venv-31210\Scripts\python.exe -m pytest tests/test_agent_bridge.py tests/test_server.py -o addopts= -p no:cacheprovider -q
```

Live checks also verified SSE tool-call conversion, MCP reading of the real
app/server.py, a second model turn identifying create_server from the tool
result, and tool selection with all eight coding-profile tools advertised.
