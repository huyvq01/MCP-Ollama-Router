# Dùng Ollama làm coding agent trong VS Code

1. Mở folder D:\MCP-Ollama-Router trong VS Code.
2. Mở extension Cline (đã cài), vào Settings / API Configuration.
3. Chọn provider Ollama, Base URL http://127.0.0.1:11434.
4. Chọn model đã tải từ danh sách. qwen2.5-coder:3b là model mặc định của router;
   model nhỏ có thể không gọi tool đúng hoặc không hoàn thành tác vụ phức tạp.
5. Bật Use Compact Prompt nếu phiên bản Cline có tùy chọn này.
6. Trong MCP Servers, kiểm tra ollama-router và nhấn Retry Connection nếu cần.
   Cấu hình stdio đã được lưu vào globalStorage của Cline; không chạy app.server riêng.
7. Giữ phê duyệt thủ công khi sửa file và chạy terminal. Bắt đầu bằng yêu cầu bên dưới.

Prompt kiểm tra:
> Gọi workspace_info, đọc app/server.py bằng read_file và giải thích ngắn bằng tiếng Việt.
> Chỉ báo cáo nội dung đã đọc thật. Chưa sửa file.

Prompt sửa code:
> Tìm nguyên nhân lỗi [mô tả lỗi]. Đọc các file liên quan, đề xuất sửa nhỏ nhất.
> Cho tôi xem propose_changes.diff trước khi áp dụng. Sau khi tôi đồng ý, áp dụng
> và chạy run_check với name=tests. Báo kết quả thực tế.

Cline là agent điều phối đọc/sửa/chạy lệnh; Ollama là model chính; MCP Router bổ sung
các công cụ có kiểm soát. Thiết lập MCP không tự đổi provider của Cline sang Ollama.

Nếu không kết nối được, mở ứng dụng Ollama trước. Kiểm tra bằng:
    ollama list
Thiếu model mặc định thì chạy (cần tải dữ liệu):
    ollama pull qwen2.5-coder:3b

Tài liệu chính thức: https://docs.cline.bot/running-models-locally/overview
