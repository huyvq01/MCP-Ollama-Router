# MCP Ollama Router — Cấu hình và hướng dẫn khởi chạy

Cập nhật: 27/10/2026. Lệnh bên dưới dùng PowerShell trên Windows.

Ghi chú bản sửa: máy hiện tại dùng bridge cổng 18082, đặt bằng
`ROUTER_BRIDGE_PORT=18082` trong `.env`; Continue apiBase cũng dùng 18082.
Mã nguồn mặc định dùng 18080 nếu không có cấu hình riêng. Trên máy mới,
đặt biến này là 18082 nếu dùng nguyên mẫu Continue trong tài liệu này.

## 1. Dự án làm gì?

Dự án cung cấp MCP tools để trợ lý trong Continue/Cline đọc và thao tác mã nguồn,
đồng thời gọi model chạy cục bộ bằng Ollama. Bridge chuyển tiếp API OpenAI tới Ollama
và chuẩn hóa phản hồi gọi tool cho Continue.

Có ba thành phần cần phân biệt:

| Thành phần | Nhiệm vụ | Cách chạy |
|---|---|---|
| Ollama — cổng 11434 | Nạp model, sinh câu trả lời | Mở ứng dụng Ollama hoặc `ollama serve` |
| Agent bridge — cổng 18082 | API model mà cấu hình Continue hiện tại sử dụng | `python scripts/portable.py bridge` |
| MCP server — stdio | Cung cấp coding tools | Continue/Cline tự khởi động theo cấu hình |

Bridge không tự thực thi tool. Continue/Cline là bên gọi MCP tool.
Nếu dùng model/provider khác trong client thì không nhất thiết cần bridge.

## 2. Cài phần mềm trên máy mới — chỉ làm lần đầu

Nếu máy có WinGet:

```powershell
winget install --exact --id Python.Python.3.12 --source winget
winget install --exact --id Ollama.Ollama --source winget
```

Đóng và mở lại terminal sau khi cài để nhận PATH mới. Nếu không có WinGet,
cài Python từ https://www.python.org/downloads/ và Ollama từ https://ollama.com/download.
Khi cài Python, bật tùy chọn thêm Python vào PATH.

Kiểm tra:

```powershell
python --version
ollama --version
```

Dự án yêu cầu Python 3.11 trở lên; các bước trong hướng dẫn dùng Python 3.12.
Không cần cài Node.js để chạy MCP server Python này.

## 3. Cài dự án — một lần trên mỗi máy hoặc sau khi di chuyển thư mục

Copy/clone mã nguồn vào thư mục bạn chọn. Máy hiện tại đang dùng:

```powershell
Set-Location -LiteralPath 'D:\MCP-Ollama-Router'
python scripts/portable.py setup
```

Trên máy khác, thay lệnh Set-Location bằng đường dẫn thật của dự án; các lệnh còn lại
không cần sửa. Có thể mở terminal ngay tại thư mục dự án để bỏ qua Set-Location.
Nếu `python` không được nhận diện nhưng có Python Launcher, dùng `py -3.12` thay thế.

Setup sẽ:

- Tạo môi trường `.venv-portable` ngay trong dự án.
- Cài dependency của dự án, không cần kích hoạt virtualenv bằng tay.
- Sinh `.local-config/mcp.json` cho MCP client.
- Sinh `.continue/mcpServers/new-mcp-server.yaml` cho Continue trong workspace.

Không copy `.venv*`, `.router-state`, `.local-config`, logs và `.env` từ máy cũ.
Không dùng cấu hình MCP đã sinh trên máy khác; chạy setup để sinh lại.
Giữ mã nguồn và `scripts/portable.py`. Cần Internet khi cài dependency và tải model.

## 4. Khởi động Ollama và tải model

Mở ứng dụng Ollama. Nếu không dùng ứng dụng, mở terminal riêng và chạy:

```powershell
ollama serve
```

Giữ terminal đó mở. Nếu báo cổng 11434 đã được sử dụng, kiểm tra API trước;
không khởi động thêm một Ollama server khi server hiện tại vẫn hoạt động.

Trong terminal khác, tải model mặc định:

```powershell
ollama pull qwen2.5-coder:3b
ollama list
```

Tải model chỉ cần làm lần đầu, hoặc khi muốn cập nhật model. Các model 7B/14B
không bắt buộc để chạy cấu hình mặc định. Chọn model cần phù hợp RAM/VRAM của máy.

## 5. Các bước start hằng ngày — dùng Continue với bridge

### Terminal 1: Ollama

Mở ứng dụng Ollama; hoặc chạy `ollama serve` như mục 4.

### Terminal 2: bridge

```powershell
Set-Location -LiteralPath 'D:\MCP-Ollama-Router'
python scripts/portable.py bridge
```

Khi thấy `Agent bridge: http://127.0.0.1:18082/v1`, giữ terminal mở.
Không đóng terminal này khi Continue còn dùng model qua bridge.
Lệnh tương đương nếu muốn dùng trực tiếp Python của dự án:

```powershell
.\.venv-portable\Scripts\python.exe -m app.agent_bridge
```

### VS Code: Continue và MCP

1. Mở thư mục dự án trong VS Code.
2. Continue đọc file `.continue/mcpServers/new-mcp-server.yaml` do setup sinh.
3. Dùng cấu hình model ở mục 7 nếu muốn gọi model qua bridge.
4. Chọn Agent để sử dụng tools; Chat không thực thi MCP tools.
5. Nếu vừa đổi cấu hình, nhấn Ctrl+Shift+P → Developer: Reload Window.

Không chạy thêm `python scripts/portable.py run` trong terminal khi client đã tự
khởi động MCP cho cùng workspace.

## 6. Cấu hình dự án tùy chọn: .env

Mặc định chạy được mà không cần tạo `.env`. Nếu muốn tùy chỉnh, chỉ tạo khi chưa có:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
notepad .env
```

Các thiết lập cơ bản:

```dotenv
ROUTER_OLLAMA_HOST=http://127.0.0.1:11434
ROUTER_BRIDGE_PORT=18082
ROUTER_DEFAULT_MODEL=qwen2.5-coder:3b
ROUTER_REPORT_MODEL=qwen2.5-coder:3b
ROUTER_NUM_CTX=4096
ROUTER_MAX_TOKENS=512
ROUTER_TIMEOUT=120
ROUTER_TRANSPORT=stdio
```

Workspace mặc định là thư mục dự án, không cần ghi cứng đường dẫn. Nếu muốn thao tác
một dự án khác, cấu hình đường dẫn thực của dự án đó:

```dotenv
# Ví dụ tùy chọn, thay bằng đường dẫn tồn tại trên máy:
# ROUTER_WORKSPACE_ROOT=C:/Projects/MyApp
# ROUTER_MENDIX_PROJECT=C:/Projects/MyApp/MyApp.mpr
# ROUTER_MENDIX_MX_EXECUTABLE=C:/Program Files/Mendix/11.6.3/modeler/mx.exe
```

Các thiết lập Mendix chỉ cần khi sử dụng tính năng Mendix. Không chia sẻ `.env`
chứa token/khóa bí mật. Biến môi trường ROUTER_* ưu tiên hơn giá trị trong `.env`.
Khởi động lại bridge/MCP sau khi thay cấu hình. Cấu hình context/token trong `.env`
áp dụng cho MCP router; Continue gửi tùy chọn riêng khi gọi model qua bridge.

## 7. Cấu hình model Continue qua bridge

Đây là mẫu để ghép vào cấu hình Continue, không ghi đè mù quáng các model/rule đang có.
Cấu hình cá nhân hiện tại nằm tại `$HOME\.continue\config.yaml`.

```yaml
name: Ollama Local Agent
version: 1.0.0
schema: v1
models:
  - name: Qwen Coder 3B Agent Bridge
    provider: openai
    model: qwen2.5-coder:3b
    apiBase: http://127.0.0.1:18082/v1
    apiKey: local-only
    roles:
      - chat
      - edit
      - apply
    capabilities:
      - tool_use
    useLegacyCompletionsEndpoint: false
    defaultCompletionOptions:
      contextLength: 4096
      maxTokens: 512
      temperature: 0
    requestOptions:
      timeout: 180000
```

`local-only` chỉ là giá trị placeholder cho client; bridge cục bộ hiện tại không yêu
cầu API key. Giữ bridge ở localhost. Mẫu này không cấu hình dịch vụ HTTP công khai.
Đổi model thì phải tải model tương ứng trước và giữ tên model nhất quán.

## 8. Kết nối Cline / sinh lại cấu hình MCP

```powershell
python scripts/portable.py config
Get-Content .local-config/mcp.json
```

Nhập/ghép phần `mcpServers` trong file này vào phần MCP Servers của Cline.
Giữ nguyên cấu hình các server khác. Không gõ lại đường dẫn Python bằng tay.
Cấu hình sinh dùng chế độ `--coding-tools` với 8 coding tools và 4 tool
`chat`, `chat_metrics`, `list_models`, `refresh_models` (12 tools).

Một workspace chỉ được một tiến trình MCP giữ khóa. Nếu dùng Continue thì tắt router
của cùng workspace trong Cline, hoặc ngược lại. Hai client có thể xung đột kể cả khi
khởi chạy bằng hai môi trường Python khác nhau. Không xóa server.lock để vượt khóa.

## 9. Kiểm tra kết nối và thử model

```powershell
# Ollama phải trả thông tin phiên bản và danh sách model
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 10
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10

# Bridge phải trả danh sách model
Invoke-RestMethod -Uri 'http://127.0.0.1:18082/v1/models' -TimeoutSec 15

# Kiểm tra model có thực sự sinh câu trả lời qua bridge
$testBody = @{
    model = 'qwen2.5-coder:3b'
    messages = @(@{ role = 'user'; content = 'Reply only OK.' })
    max_tokens = 8
    stream = $false
} | ConvertTo-Json -Depth 6
$testResult = Invoke-RestMethod -Method Post `
    -Uri 'http://127.0.0.1:18082/v1/chat/completions' `
    -ContentType 'application/json' -Body $testBody -TimeoutSec 180
$testResult.choices[0].message.content
```

Kiểm tra cổng/model đang được nạp:

```powershell
netstat -ano -p tcp | Select-String ':11434|:18082'
ollama ps
```

## 10. Các lệnh quản lý dự án

Chạy MCP thủ công để chẩn đoán, sau khi đã ngắt MCP trong client:

```powershell
python scripts/portable.py run --coding-tools
```

Muốn bật đầy đủ MCP tools khi chạy thủ công:

```powershell
python scripts/portable.py run
```

MCP stdio đợi client trao đổi dữ liệu, không có giao diện web; terminal đang chờ
không tự có nghĩa là server bị treo. Nhấn Ctrl+C để dừng tiến trình chạy foreground.

Sau khi cập nhật mã nguồn, chạy lại:

```powershell
python scripts/portable.py setup
```

Cài công cụ phát triển và chạy bộ kiểm thử không phụ thuộc Ollama:

```powershell
python scripts/portable.py setup --dev
.\.venv-portable\Scripts\python.exe -m pytest -o addopts= -q --ignore=tests/test_engine.py --ignore=tests/test_router.py --ignore=tests/test_selector.py --ignore=tests/test_registry.py --ignore=tests/test_provider.py
.\.venv-portable\Scripts\python.exe -m ruff check app scripts/portable.py tests/test_portable.py
```

Các kiểm thử live cần Ollama/model hoạt động; smoke script MCP còn cần workspace
không bị MCP client khác giữ khóa.

## 11. Ghi chú xử lý lỗi

| Thông báo | Kiểm tra / cách xử lý |
|---|---|
| Connection error trong chat Continue | Kiểm tra bridge 18082 đã chạy và apiBase đúng; sau đó kiểm tra Ollama 11434 |
| 502 Ollama request failed / Ollama unavailable | Kiểm tra API Ollama và thử model trực tiếp; bridge có thể đang chạy nhưng Ollama chưa chạy, không phản hồi hoặc lỗi kết nối |
| MCP -32000 Connection closed | Kiểm tra router có đang chạy trong Cline/Continue khác không; tắt bản trùng và reload VS Code |
| Another MCP server owns this workspace | Chỉ giữ một MCP server cho workspace; không xóa file khóa khi tiến trình còn sống |
| All tools disabled in Chat | Chuyển Continue sang Agent để gọi tool |
| Model not found | Chạy `ollama list`, sau đó `ollama pull qwen2.5-coder:3b` nếu thiếu |
| Cổng đã được sử dụng | Kiểm tra API và PID bằng netstat; dùng tiến trình đang chạy nếu hoạt động tốt |
| Python không tìm thấy | Mở terminal mới sau khi cài, kiểm tra PATH hoặc thử `py -3.12` |
| Access denied khi dừng Ollama | Thoát Ollama ở khay hệ thống; nếu cần, mở Task Manager bằng Administrator và chỉ kết thúc đúng tiến trình Ollama |

Sau khi khởi động lại máy, luôn kiểm tra Ollama và chạy lại bridge trước khi dùng
Continue với cấu hình model qua bridge. Không cần setup hoặc tải model lại mỗi ngày.

## 12. Nguồn tham khảo

- Mã nguồn dự án: `scripts/portable.py`, `.env.example`, `app/agent_bridge.py`.
- Ollama: https://docs.ollama.com/quickstart
- Gói Ollama trong WinGet: https://github.com/microsoft/winget-pkgs/tree/master/manifests/o/Ollama/Ollama
- Gói Python 3.12 trong WinGet: https://github.com/microsoft/winget-pkgs/tree/master/manifests/p/Python/Python/3/12


Bridge đã bổ sung hiển thị nguyên kết quả tool khi model trả rỗng hoặc lặp lại
cùng tool vừa hoàn tất. Thử lại trong chat mới sau khi cấu hình Continue nạp lại.


## Hỏi bằng ngôn ngữ tự nhiên

Trong Agent, bạn có thể hỏi `Phân tích giúp tôi file message.py`, `Tìm hàm build`,
`Chạy kiểm thử dự án` hoặc `Viết báo cáo ngắn về kiểm thử`. Không cần ghi read_file,
chat hay JSON. Bridge tự chọn các bước chuẩn, còn Continue thực thi tool theo quyền
bạn đã đặt. Khi file trùng tên hoặc yêu cầu thiếu thông tin, hệ thống sẽ hỏi lại.
Với sửa mã, bản diff được hiển thị trước; có thể trả lời `đồng ý áp dụng` sau khi xem.
Xem CONTINUE_AGENT.md trong thư mục dự án để biết chi tiết và giới hạn.
