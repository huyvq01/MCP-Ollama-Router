# Hướng dẫn thử nghiệm nội bộ – phiên bản 0.2.0

Đây là bản để pilot trên máy cá nhân/nhóm thử nghiệm tin cậy. Không phải chứng
nhận production, bảo mật hoặc chất lượng câu trả lời. Chưa triển khai dịch vụ
trên mạng công ty. Model local không tự có quyền đọc/sửa file: Cline thực hiện
các thao tác đó qua công cụ và quyền của Cline.

## 1. Cài đặt

Yêu cầu Python 3.11 hoặc 3.12, Ollama đang chạy và có model chat phù hợp.
Máy hiện tại đã kiểm tra bằng Python 3.11.9 trên Windows. CI được cấu hình
thêm Python 3.12; chưa coi đó là kết quả chạy CI thực tế.

Mở PowerShell tại thư mục source đã giải nén:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]" -c constraints-windows-py311.txt
.\.venv\Scripts\python.exe -m pip check
```

File constraints ghi lại dependency đã có trên Windows/Python 3.11. Không dùng
nguyên file đó để khẳng định hỗ trợ mọi OS/Python. Với Python 3.12/Linux,
cài `-e ".[test]"` rồi chạy lại bộ test. Dependency và model tải lần đầu có
thể cần Internet/kho package nội bộ; chạy suy luận không cần gọi cloud.

## 2. Chọn một cách kết nối

### A. Giữ MCP stdio

```powershell
.\.venv\Scripts\python.exe -m app.server
```

AI client quản lý subprocess stdio. Cấu hình command là đường dẫn đầy đủ đến
`.venv\Scripts\python.exe`, args là `-m app.server`, và đặt working directory
về thư mục source (hoặc cài package editable trước). Không thêm banner vào
stdout. Log JSON được gửi sang stderr.

`chat` tự chọn model, prompt theo công việc và ngân sách trả lời. `route_preview`
cho xem kế hoạch mà không sinh câu trả lời. Cline đọc file trước, gửi đoạn
code liên quan sang `chat`, rồi áp dụng sửa đổi bằng công cụ của Cline.

### B. Dùng router làm model provider cho Cline

Gateway này hỗ trợ một phần API chat completions, không phải toàn bộ OpenAI API.
Nó giữ nguyên system prompt/tool result của client, chuyển tiếp function tools,
trả tool calls và streaming SSE. Server không thực thi tool do model yêu cầu.

1. Sao chép `.env.example` thành `.env` nếu chưa có. Không ghi đè cấu hình cũ.
   Bản editable tìm `.env` tại source root; bản wheel tìm ở thư mục làm việc.
   Có thể đặt biến môi trường `ROUTER_ENV_FILE` thành đường dẫn cấu hình cụ thể.
2. Sinh API key bằng lệnh dưới, rồi nhập key vào `ROUTER_GATEWAY_API_KEY` trong
   `.env`. Không gửi key vào chat, commit hoặc log:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
.\.venv\Scripts\python.exe -m app.gateway
```

3. Trong Cline chọn provider tương thích OpenAI:

| Cấu hình | Giá trị |
|---|---|
| Base URL | `http://127.0.0.1:8080/v1` |
| API key | Key vừa tạo trong `.env` |
| Model ID | `auto` |
| Context window | `8192`, khớp `ROUTER_GATEWAY_CONTEXT_TOKENS` |
| Max output | Không quá `2048` |

4. Mở đúng workspace. Cho phép đọc file; duyệt các đề xuất sửa/chạy lệnh theo
   quy định công ty. Bỏ rule bắt buộc gọi MCP `chat` cho mọi câu khi đã dùng
   gateway làm provider: rule đó sẽ tạo thêm lượt suy luận. Có thể ngắt riêng
   MCP router khi thử gateway; công cụ file native của Cline vẫn cần được bật.
5. Bắt đầu với yêu cầu nhỏ: đọc README, tóm tắt một hàm, sửa một lỗi có test.

Chưa xác minh end-to-end trên UI Cline hoặc mọi model/tool-call format.
Nếu Cline gửi tính năng ngoài subset (ví dụ tool_choice bắt buộc, n>1,
parallel_tool_calls=false, ảnh/audio), gateway trả HTTP 400 thay vì bỏ qua.
Nếu tool definitions + lịch sử quá dài, gateway trả `context_length_exceeded`;
không cắt mất system prompt hay tool result. Giảm phạm vi nhiệm vụ/lịch sử,
hoặc tăng context ở cả gateway và Cline sau khi đo RAM/tốc độ. Một số workload
agent cần 16K–32K; máy 16 GB CPU có thể không đạt độ trễ chấp nhận được.

## 3. Kiểm thử tự động

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration"
.\.venv\Scripts\python.exe -m app.evaluate --out evaluation-routing.json
```

Unit tests dùng upstream giả lập, không gửi code ra ngoài và không cần GPU.
Routing evaluation dùng 13 câu hỏi tổng hợp được viết thủ công; đạt 13/13
không có nghĩa là đạt chất lượng ngữ nghĩa trên dữ liệu thực tế.

## 4. Đo suy luận thật (chỉ chạy khi đã bật gateway)

```powershell
.\.venv\Scripts\python.exe -m app.evaluate --live --limit 3 --out evaluation-live.json
```

Mặc định chỉ lưu kết quả routing, model, thời gian ra nội dung đầu tiên,
tổng thời gian và usage. Mỗi câu giới hạn 128 token để đo ngắn, không dùng
để chấm độ đầy đủ của code. Thêm `--include-answers` chỉ khi được phép lưu
câu trả lời. Script không tự chạy code model sinh ra.

Đo riêng lượt đầu (cold load) và lượt sau (warm load). `keep_alive` chỉ giảm
nạp lại, không tăng tốc sinh token. Chuyển giữa nhiều model vẫn có thể chậm
trên CPU. Không dùng log của mock tests để suy ra tốc độ model thực tế.

## 5. Tiêu chí nghiệm thu do nhóm thử nghiệm chốt trước

- Bộ test tự động đạt; lỗi auth, context và overload trả đúng trạng thái.
- Cline thực sự gọi tool đọc file, áp dụng patch và chạy test, không chỉ nói đã làm.
- Chạy riêng một bộ bài của công ty: sửa bug có test, giải thích code, viết tài liệu.
- Hai người review tính đúng, độ đầy đủ, giả định và API do model đề xuất.
- Đặt ngưỡng p50/p95, thời gian ra token đầu, RAM và tỷ lệ lỗi trước khi đo;
  không có một ngưỡng phù hợp cho mọi máy hoặc mọi model.
- Ghi tên/digest model, bản Ollama, phần cứng, cấu hình context, cold/warm,
  độ dài input/output và phiên bản source để có thể so sánh lại.

## 6. Giới hạn vận hành

- Mặc định 1 inference đồng thời, tối đa 8 request đã nhận, queue wait 5 giây,
  deadline toàn request 90 giây, tối đa 2 lần thử, attempt timeout 45 giây.
  Với streaming, attempt timeout bao việc mở upstream; toàn stream vẫn chịu
  deadline request và read timeout. Sau khi phát dữ liệu sẽ không fallback
  sang model khác để tránh trộn câu trả lời.
- Circuit breaker tạm bỏ qua model lỗi liên tục; reset sau cooldown.
- MCP lưu tối đa 256 phiên, TTL 1 giờ, số message và token mỗi phiên có giới hạn.
  Clear trong khi request chạy sẽ ngăn lượt cũ ghi lại vào phiên đã xóa.
- Gateway không lưu lịch sử hội thoại; client gửi lịch sử cần thiết. Không có
  response cache dùng chung hoặc tự động lưu code/câu trả lời ra file.
- Ngân sách token là ước lượng UTF-8, không phải tokenizer chính xác của model.
  Giữ khoảng trống và đo với model/ngôn ngữ thật. Input quá lớn bị từ chối,
  không được mô tả như đã review đầy đủ.
- Kích thước model dựa metadata. Với file mẫu, model không rõ kích thước bị
  loại; ngưỡng mặc định 8B. Tag `8b` nhưng metadata `8.2B` vẫn vượt ngưỡng.
  `MAX_ROUTER_MODEL_B` đã được thay bằng biến `ROUTER_MAX_MODEL_BILLIONS`.
- Gateway chỉ bind localhost mặc định và yêu cầu bearer key. Chưa có SSO/RBAC,
  tenant isolation, distributed queue/rate limit, TLS termination hoặc HA.
  API key dùng chung không phải ranh giới đa tenant. Chạy một worker. Dừng
  cả MCP subprocess nếu muốn chỉ một inference trên toàn máy: hai process
  không chia sẻ semaphore hay circuit breaker.
- Không mở public/LAN trước khi nhóm hạ tầng thiết kế auth/TLS, network ACL,
  kiểm thử tải và kiểm tra chính sách dữ liệu. Thay model không thay thế việc
  kiểm thử code sinh ra trong môi trường test tách biệt của công ty.
- `.gitignore` không tự bỏ theo dõi file đã commit. Repo cũ có `.venv`, cache
  và artifact được Git theo dõi; bản ZIP sạch không chứa chúng. Review index
  và lịch sử trước khi đưa repo gốc lên hệ thống quản lý source của công ty.

## 7. Health và lỗi

`GET /health/live` chỉ cho biết process chạy. `GET /health/ready` yêu cầu key,
kiểm tra provider và ít nhất một model phù hợp. `/v1/models` yêu cầu key.
Health không chứng minh model có thể hoàn thành mọi bài suy luận.

| HTTP | Ý nghĩa |
|---|---|
| 400 | Request/tính năng/context/model không hợp lệ |
| 401 | API key thiếu/sai |
| 413 | Request body quá lớn |
| 429 | Hàng đợi đầy hoặc chờ quá lâu |
| 502 | Ollama lỗi hoặc trả protocol không hợp lệ |
| 503 | Chưa cấu hình key hoặc không có model phù hợp |
| 504 | Hết thời hạn request |

Gateway trả model thực tế và `X-Request-ID`. Lỗi giữa stream được gửi thành
SSE error + `[DONE]`; phần nội dung trước lỗi có thể chưa hoàn chỉnh. Dùng
request ID, thời điểm và loại lỗi để điều tra; không bật log prompt/secret.
