# Báo cáo xác minh company pilot 0.2.0

Ngày 24/10/2026. Đã chạy trên Windows, CPython 3.11.9, Ollama local.
Phạm vi: source để thử nghiệm một người dùng trên localhost. Chưa triển khai
server công ty hoặc cấu hình lại Cline của người dùng.

## Kết quả đã kiểm chứng

| Hạng mục | Kết quả |
|---|---|
| Unit/contract tests | 139 đạt, 0 lỗi; 9 integration tests không chạy |
| Statement coverage toàn app | 83.1% |
| Gateway statement coverage | 86.4% |
| Router engine statement coverage | 89.8% |
| Phân loại câu hỏi tổng hợp | 13/13 |
| Ruff F/E9 trên app, tests, packager | Đạt |
| Parse toàn bộ source Python | Đạt |
| pip check | Không có dependency hỏng |
| Cài editable + test extra theo constraints, offline | Đạt trong venv hiện có |
| Build wheel và kiểm tra nội dung | Đạt; có eval_cases, không có env/log/cache |
| Gateway readiness/catalog với Ollama thật | HTTP 200 |

Đây là statement coverage, không phải branch coverage. CI đã cấu hình Python
3.11/3.12 nhưng chưa chạy GitHub trong phiên này. Cài vào venv hiện có không
chứng minh cài mới thành công trên một máy công ty sạch; cần chạy lại tại đó.

## Phép thử suy luận thật

Chỉ dùng prompt tổng hợp, không dùng code/tài liệu công ty. Gọi gateway trong
process bằng ASGI transport, chưa test UI Cline hoặc TCP listener/reverse proxy.
Không có tool do model yêu cầu nào được thực thi.

- Lượt trả lời ngắn đầu tiên: gemma3:4b, HTTP 200,
  12.218 giây, 3 completion tokens.
- Streaming lượt sau: gemma3:4b, HTTP 200,
  1.347 giây tổng thời gian, trả đúng “OK”, finish_reason=stop.
- Native ping tool-call probe, auto chọn qwen2.5-coder:7b:
  HTTP 502, 20.024 giây,
  `upstream_unavailable`, attempt timeout 20 giây của phép thử.

Hai phép đo ngắn không phải benchmark thống kê hoặc TTFT; không suy ra p95
hay tốc độ cho prompt dài. Lượt nhanh hơn khi model còn được nạp không chứng
minh mọi model đều nhanh. Probe ping chưa hoàn tất nên CHƯA xác nhận native
tool calling của model 7B hoặc luồng đọc/sửa file end-to-end trong Cline.
Timeout probe 20 giây ngắn hơn 45 giây mặc định của source; không kết luận
model không hỗ trợ tools chỉ từ một lần timeout. Cần đo lại trên máy mục tiêu,
chọn model tool-capable được xác minh và chốt SLA thực tế.

## Thay đổi chính

- Cấu hình .env có validation; pin dependency chính và closure Windows/Python 3.11.
- Tổng deadline, giới hạn attempts, bounded admission/queue và circuit breaker.
- Serialize phiên MCP; ghi user/assistant atomically; TTL/LRU/token limits;
  clear trong lúc request chạy không làm lịch sử cũ xuất hiện lại.
- Quy tắc routing Việt/Anh, task prompt, ngân sách token và native tool eligibility.
- Gateway bearer auth, SSE, function-call/tool-result conversion, input/context
  limits và request ID. Không cắt mất system prompt hay tool result của agent.
- JSON logs stderr không ghi prompt, câu trả lời hoặc session ID thô.
- Source release sạch, SHA-256 manifest và hướng dẫn thử nghiệm nội bộ.

## Phần chưa được chứng minh

- Chất lượng/sự đúng của code, tài liệu và giả định trên corpus công ty.
- Cline thực sự đọc file, áp dụng patch và chạy test với model được chọn.
- Cold/warm latency, RAM/GPU, p50/p95 và tải thực trên phần cứng mục tiêu.
- Môi trường cài mới, Python/OS khác và kết quả CI ngoài máy hiện tại.
- SSO/RBAC, multi-tenant isolation, TLS, distributed limits, HA hoặc pentest.

Đây là single-tenant local pilot, không phải chứng nhận production hoặc chất
lượng model. Quyền đọc/sửa file do Cline quản lý. Source không tự chạy code
model sinh ra. Xem docs/COMPANY_TEST.md để cài đặt, test và nghiệm thu.

ZIP sạch không chứa .env, .venv, model weights, log hoặc Git history.
uv.lock cũ không còn khớp đã được thay bằng pyproject + constraints; có bản
sao lưu trong thư mục work của phiên làm việc, không đưa vào release.
