# Continue: yêu cầu bằng ngôn ngữ tự nhiên

Chọn Agent và model `Qwen Coder 3B Agent Bridge` trong Continue. Không cần ghi tên
tool, JSON hoặc session_id trong câu hỏi thường ngày.

Ví dụ:

- `Phân tích giúp tôi file message.py`.
- `Giải thích app/server.py làm gì`.
- `Tìm hàm build trong dự án`.
- `Liệt kê các file Python`.
- `Chạy kiểm thử dự án giúp tôi`.
- `Viết báo cáo ngắn về lợi ích của kiểm thử phần mềm`.
- `Sửa hello.py để giá trị value bằng 2, cho tôi xem bản thay đổi`.

## Cách xử lý

Bridge tự chọn bước tiếp theo từ những MCP tools Continue cung cấp. Nếu chỉ có
tên file, nó tìm đường dẫn trước rồi đọc nội dung thật; nếu trùng tên thì hỏi lại.
Khi phân tích, nó dùng dữ liệu đã đọc để tạo giải thích, không chỉ chép lại file.
Yêu cầu tìm symbol dùng công cụ tìm mã; yêu cầu kiểm thử dùng tên check mà
workspace_info đã xác nhận. Nó không tự đoán lệnh shell.

Viết báo cáo được chuyển sang MCP chat với mode=auto, không ép model. Router dùng
ROUTER_REPORT_MODEL cho báo cáo và ROUTER_DEFAULT_MODEL cho các câu hỏi khác qua
MCP chat. Điều này không có nghĩa mọi lượt của model điều khiển đều chuyển sang 7B.
Có thể hỏi `Model nào vừa trả lời?` sau lần viết báo cáo trong cùng cuộc trò chuyện.

Sửa file vẫn theo luồng đọc → đề xuất diff → bạn xem → xác nhận `đồng ý áp dụng`.
Client tiếp tục thực thi tool và giữ chính sách Ask First/Automatic bạn đã chọn.
Bridge không tự đọc ổ đĩa, không tự thực thi tool và không bỏ qua quyền của client.
Các yêu cầu phức tạp ngoài các luồng chuẩn vẫn do model lập kế hoạch; yêu cầu chưa
rõ hoặc có nhiều file cùng tên cần bạn bổ sung thông tin.

## Khởi động

```powershell
python scripts/portable.py bridge
```

Cổng được đọc từ ROUTER_BRIDGE_PORT trong .env, mặc định 18080. apiBase của model
Continue phải trỏ cùng cổng với hậu tố /v1. Không chạy hai bridge trên cùng cổng.
Ollama cần đang chạy. Continue/Cline tự khởi động MCP stdio từ cấu hình đã sinh;
chỉ một tiến trình MCP cho cùng workspace.

ROUTER_BRIDGE_AUTO_TOOLS=true bật chọn bước tự động (mặc định); false chỉ chuyển
request qua Ollama như trước. Trong Chat, Continue không cung cấp tools nên các
hành động này không chạy. Dùng Agent và mở chat mới sau khi đổi cấu hình.

## Xác minh

Kiểm thử tự động:

```powershell
python scripts/portable.py setup --dev
.\.venv-portable\Scripts\python.exe -m pytest tests/test_agent_workflow.py tests/test_agent_bridge.py -o addopts= -q
```

Xem các khối tool call trong Continue để biết hành động thật. Đừng coi JSON do model
tự viết hoặc lời khẳng định đã đọc/sửa file là bằng chứng thực thi.
