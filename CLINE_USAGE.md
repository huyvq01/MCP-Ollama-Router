# Sử dụng qua Cline

Sau khi cập nhật source: nhấn Retry Connection cho ollama-router hoặc Reload Window trong VS Code.

Mẫu yêu cầu Cline:

> Dùng tool chat của ollama-router. Để trống model để dùng bản 3B nhanh.
> Dùng mode=code cho Java/Mendix, mode=report cho báo cáo tiếng Việt.
> Gửi phần mã/tài liệu liên quan, không gửi toàn bộ repository.
> Trả lời ngắn; max_tokens=384 cho câu hỏi nhỏ, 512 thông thường.
> Báo cáo dài chia từng mục, có thể dùng max_tokens=1536 cho một mục.
> Dùng cùng session_id khi hỏi tiếp cùng chủ đề.
> Không chọn model 7B trừ khi tôi yêu cầu.

Mỗi lần gọi tool chờ nội dung hoàn tất. Giới hạn đầu ra thấp giúp trả lời nhanh,
nhưng có thể cắt phần cuối: kiểm tra chat_metrics.finish_reason; length nghĩa là
đã chạm giới hạn. Khi đó hỏi tiếp hoặc tăng max_tokens cho lần gọi sau.

Model Cline chính và model của MCP là hai luồng khác nhau. Nếu Cline chậm trước
khi gọi tool hoặc sau khi tool trả kết quả, cần kiểm tra provider/model chính
của Cline. MCP này không thay đổi provider chính của Cline.

Không tự động bật autoApprove. Tool chat không đọc/sửa file hoặc tra web;
Cline cần cung cấp trích đoạn và tài liệu Mendix đúng phiên bản.
