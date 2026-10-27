# MCP Ollama Router

MCP server for local Ollama, with a portable Python bootstrap for Windows, Linux and macOS.

## Cài đặt trên máy mới

Cài Python 3.11+ và Ollama, rồi clone/copy mã nguồn vào bất kỳ thư mục nào.
Không copy các thư mục `.venv*`, `.router-state`, `.local-config`, logs hoặc `.env`
của máy cũ. Môi trường Python cần được tạo riêng trên từng máy.

Chạy tại thư mục dự án (PowerShell, bash hoặc terminal):

```sh
python scripts/portable.py setup
ollama pull qwen2.5-coder:3b
python scripts/portable.py run
```

Nếu hệ thống dùng tên `python3`, thay `python` bằng `python3`. Ollama phải đang chạy.
`setup` tạo `.venv-portable`, cài dependency đã pin và sinh cấu hình theo đường dẫn
máy hiện tại. Cần Internet khi cài dependency và tải model lần đầu.
Không cần sửa đường dẫn trong mã nguồn. Chạy lại `setup` sau khi cập nhật code;
chạy lại `setup` ở vị trí mới nếu di chuyển thư mục. Lệnh setup không tải model tự động.

## Kết nối MCP client

Continue: mở thư mục dự án rồi chạy `setup`; cấu hình cục bộ được sinh tại
`.continue/mcpServers/new-mcp-server.yaml`. Kết nối lại Continue sau khi cài đặt.

Cline hoặc client stdio khác: nhập/ghép nội dung `.local-config/mcp.json` do `setup`
sinh vào phần MCP của client, giữ các server khác đang có. Đây là bước đăng ký
client một lần trên mỗi máy; không phải sửa đường dẫn thủ công. Client tự khởi động
server; không cần chạy thêm `run` trong terminal. Cấu hình sinh giữ chế độ `--coding-tools` như Continue trước đây.
Cấu hình sinh tự động không mang
sang máy khác; chạy `setup` để tạo lại.

Các lệnh khác:

```sh
python scripts/portable.py bridge
python scripts/portable.py config
python scripts/portable.py setup --dev
```

`bridge` chạy adapter OpenAI tại cổng 18080. `config` sinh lại cấu hình.
Đường dẫn Python và thư mục làm việc được tính từ vị trí mã nguồn, không phụ thuộc
ổ D:, tên người dùng hoặc phiên bản thư mục virtualenv cũ.
Sau khi kích hoạt `.venv-portable`, cũng có thể dùng `mcp-ollama-router` và
`mcp-ollama-bridge`.

## Lỗi Connection closed khi dùng nhiều client

Mỗi workspace chỉ cho phép một tiến trình MCP để tránh hai client cùng ghi file.
Nếu Cline đã kết nối router của workspace này, hãy tắt server đó trong Cline trước
khi kết nối Continue (hoặc ngược lại), rồi reload cửa sổ VS Code.
Không xóa `server.lock` để vượt khóa của tiến trình đang chạy.
Cấu hình sinh tự động gọi Python trực tiếp với `-m app.server`, giữ tiến trình
stdio gắn với client trên Windows.

## Cấu hình tùy chọn

Mặc định dùng Ollama cục bộ tại `http://127.0.0.1:11434` và workspace là thư mục
mã nguồn. Không cần `.env` để chạy mặc định. Nếu dùng Ollama ở máy khác, đặt
`ROUTER_OLLAMA_HOST`; cả MCP server và bridge đều dùng giá trị này.
`.env.example` liệt kê các tùy chọn, không chứa đường dẫn riêng của máy tác giả.
Không chia sẻ `.env` chứa khóa bí mật. Mendix và workspace ngoài dự án vẫn cần
đường dẫn thực trên máy sử dụng nếu bật những tính năng đó.

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
.venv-portable/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv-portable/Scripts/python.exe -m pytest -o addopts= -q
.venv-portable/Scripts/python.exe -m scripts.test_mcp
```


Runtime dependency versions are pinned to the tested environment in requirements.txt and pyproject.toml. uv.lock has been refreshed. Create virtual environments locally with the portable setup command. Vietnamese usage instructions are in CLINE_USAGE.md.


## Repository / online / authenticated HTTP tools (v1.2)

See AGENT_GUIDE.md for configuration and examples.

~~~powershell
.venv-portable/Scripts/python.exe -m scripts.test_agent_mcp
.venv-portable/Scripts/python.exe -m scripts.test_http_mcp
~~~

31 tools include confined repository access/review, reviewed changes with
rollback/recovery, named checks, controlled Git, public documentation retrieval
and scoped JWT HTTP. This update does not publish code or change credentials.

## Mendix 11.6.3 model reading and reports

Ten additional MCP tools export saved Mendix models with mx dump-mpr, index units,
read confined source and produce resumable Ollama reports. See [MENDIX_USAGE.md](MENDIX_USAGE.md).
Existing repository workspace and checks are preserved. No MPR editing is included.


## Kiểm chứng model thực tế trong Continue

Chế độ `--coding-tools` gồm 8 coding tools cùng `chat`, `chat_metrics`,
`list_models`, `refresh_models` (12 tools). Sau khi cập nhật, reconnect MCP hoặc
reload VS Code và dùng Agent. Gọi `chat` trước, không truyền `model`, rồi gọi
`chat_metrics` với cùng `session_id`. Trường `model` trong phản hồi thực của tool
cho biết model đã trả lời. Metrics nằm trong bộ nhớ tiến trình; reload server sẽ
xóa metrics. Văn bản JSON do model tự viết không phải bằng chứng tool đã chạy.
Model của Continue qua bridge và model do MCP router chọn là hai luồng riêng.


## Bridge: câu trả lời trống sau khi gọi tool

Bridge hiển thị nguyên kết quả tool vừa hoàn tất nếu model trả nội dung rỗng hoặc
lặp lại chính xác tool/arguments vừa chạy. Kết quả được đối chiếu bằng tool_call_id
trong cùng lượt hội thoại; không tái sử dụng sau một câu hỏi mới. Bridge không
thực thi tool và không tự bịa câu trả lời. Câu trả lời bình thường hoặc yêu cầu
gọi tool mới vẫn giữ nguyên. Sau khi cập nhật bridge, khởi động lại tiến trình
`python scripts/portable.py bridge` để áp dụng.


Cổng bridge có thể đặt bằng `ROUTER_BRIDGE_PORT` trong `.env` (mặc định 18080).
Máy hiện tại dùng 18082 để tránh tiến trình bridge cũ không thể dừng do quyền Windows;
apiBase của model Continue đã được đổi sang `http://127.0.0.1:18082/v1`.
Lệnh `python scripts/portable.py bridge` tự đọc cổng này. Cấu hình model Continue
và cổng bridge phải khớp nhau. Cổng Ollama vẫn là 11434.


## Natural-language Agent workflows

Use Agent mode and ask normally: `Phân tích file message.py`, `Tìm hàm build`,
`Chạy kiểm thử dự án` or `Viết báo cáo ngắn về kiểm thử`. The bridge plans common
read/search/check/report steps from advertised tool schemas; the client executes
them. Basenames are resolved before reading, ambiguous names require clarification,
and checks use configured names. Analysis uses actual file evidence. Changes are
proposed as diffs and require approval before application. Complex requests outside
these standard flows remain model-planned; there is no guarantee for arbitrary tasks.
See CONTINUE_AGENT.md. Disable the workflow with ROUTER_BRIDGE_AUTO_TOOLS=false.
