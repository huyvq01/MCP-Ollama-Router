# MCP Ollama Router

Optimized for Python 3.12.10, i7-10750H, 32 GB RAM and a 4 GB Quadro T2000.

## Install and start (PowerShell)
```powershell
ollama pull qwen2.5-coder:3b
.\.venv-31210\Scripts\python.exe -m pip install -e .
.\.venv-31210\Scripts\python.exe -m app.server
```
The server uses stdio. Cline starts it automatically; do not start an extra process for Cline.

## Cline configuration
```json
{"mcpServers":{"ollama-router":{"command":"D:\\MCP-Ollama-Router\\.venv-31210\\Scripts\\python.exe","args":["-m","app.server"],"cwd":"D:\\MCP-Ollama-Router","timeout":150,"disabled":false,"autoApprove":[]}}}
```
Reconnect Cline after changing code/configuration. The main Cline model and this MCP assistant are separate: speeding up this tool does not speed up Cline's own model calls.

## Tuning
Settings read `.env` in the repository and `ROUTER_*` environment variables (environment wins). Existing unrelated .env keys are ignored. Defaults:
```dotenv
ROUTER_DEFAULT_MODEL=qwen2.5-coder:3b
ROUTER_REPORT_MODEL=qwen2.5-coder:3b
ROUTER_NUM_CTX=4096
ROUTER_MAX_TOKENS=512
ROUTER_TIMEOUT=120
ROUTER_KEEP_ALIVE=10m
ROUTER_MAX_HISTORY=8
ROUTER_MAX_SESSIONS=64
```
One local model handles both code and reports to avoid swapping weights on a 4 GB GPU. Select 7B explicitly only when its extra latency is acceptable. `chat` accepts `mode=code|report|auto`, `max_tokens`, `temperature`, and an explicit model. Reports should be generated section by section using supplied project evidence. No web retrieval or Mendix project parser is included. Never invent citations.

Context budgeting uses conservative UTF-8 byte counts, not an exact tokenizer: old complete turns are dropped, and oversized current prompts are rejected with a useful error. Output defaults to 512 tokens; use `chat_metrics` to inspect `finish_reason=length` before continuing. GPU has one active router request; overload is rejected rather than queued indefinitely. Requests have a shared 120-second deadline. No prompt/answer text is logged.

Use `refresh_models` after downloading models. Inspect GPU offload with `ollama ps`. Provider settings explicitly send 4096 context even if Ollama/model defaults are larger. Ollama environment settings must be applied to the Ollama process, not just Cline.

## Validate
```powershell
.\.venv-31210\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-31210\Scripts\python.exe -m pytest -o addopts= -q
.\.venv-31210\Scripts\python.exe -m scripts.test_mcp
```
Original modified files are copied under `backups/` before optimization.

Runtime dependency versions are pinned to the tested environment in requirements.txt and pyproject.toml. uv.lock has been refreshed. The old .venv was copied from another computer; always use .venv-31210. Vietnamese usage instructions are in CLINE_USAGE.md.


## Repository / online / authenticated HTTP tools (v1.2)

See AGENT_GUIDE.md for configuration and examples.

~~~powershell
.\.venv-31210\Scripts\python.exe -m scripts.test_agent_mcp
.\.venv-31210\Scripts\python.exe -m scripts.test_http_mcp
~~~

31 tools include confined repository access/review, reviewed changes with
rollback/recovery, named checks, controlled Git, public documentation retrieval
and scoped JWT HTTP. This update does not publish code or change credentials.

## Mendix 11.6.3 model reading and reports

Ten additional MCP tools export saved Mendix models with mx dump-mpr, index units,
read confined source and produce resumable Ollama reports. See [MENDIX_USAGE.md](MENDIX_USAGE.md).
Existing repository workspace and checks are preserved. No MPR editing is included.
