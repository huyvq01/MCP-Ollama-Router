# Đọc Mendix 11.6.3 và báo cáo với Ollama

Giữ nguyên cấu hình MCP/Cline hiện có (`-m app.server`). Không cần đổi
ROUTER_WORKSPACE_ROOT, không chạy thêm server cho cùng workspace. Kết nối lại
MCP trong Cline sau khi nâng cấp. Chỉ mô hình đã lưu trên đĩa được đọc; hãy Save
trong Studio Pro trước khi xuất và tránh lưu mô hình trong lúc xuất.

## Cấu hình riêng cho Mendix

Các giá trị sau nằm trong `.env` của router, môi trường process có ưu tiên cao hơn:

```dotenv
ROUTER_MENDIX_PROJECT=D:/Mobino/THG_LotusPrd_26/THM_Lotus.mpr
ROUTER_MENDIX_MX_EXECUTABLE=C:/Program Files/Mendix/11.6.3/modeler/mx.exe
ROUTER_MENDIX_EXPORT_TIMEOUT=600
ROUTER_REPORT_MODEL=qwen2.5-coder:3b
```

Workspace code hiện tại và named checks Python không thay đổi. Công cụ
`mendix_list_sources`/`mendix_read_source` dùng thư mục Mendix riêng, chỉ đọc
Java/JS/TS/XML/style trong javasource, javascriptsource, theme, themesource.
Không đưa cấu hình tài khoản, dữ liệu chạy ứng dụng hoặc khóa vào prompt.

## Yêu cầu mẫu cho Cline

> Dùng MCP ollama-router, gọi mendix_info để xác nhận đúng dự án. Gọi
> mendix_start_export(modules="AMS"), lưu export_id và gọi mendix_export_status
> cách vài giây đến khi completed. Nếu failed/interrupted, báo lỗi rồi dừng.
> Gọi mendix_list_units(export_id=..., query="ACT_LiquidationAsset_ShowDetail").
> Dùng ID trả về để gọi mendix_read_unit, sau đó mendix_start_report.
> Lưu report_id và gọi mendix_report_step từng bước khi pending.
> Nếu retry_required, xem lỗi; chỉ chờ và thử lại nếu router bận.
> Khi completed, đọc hết mendix_report_status bằng offset/limit và tổng hợp
> báo cáo tiếng Việt. Phân biệt dữ kiện, nghi vấn và phần thiếu bằng chứng.
> Dẫn tên/ID unit và dòng JSON xuất; không gọi đó là dòng Java.
> Nêu đoạn bị cắt theo metrics.finish_reason=length. Không sửa source/model.

Đổi module và query để xem nghiệp vụ khác. Chỉ báo cáo một unit/lần trước khi
mở rộng. Quét tất cả microflow của AMS bằng model 3B sẽ cần nhiều lượt và có
thể lâu. Không tự suy luận rằng đã đọc toàn ứng dụng từ vài đoạn.

## Công cụ mới

- mendix_info: đường dẫn và loại tài liệu hỗ trợ.
- mendix_start_export / mendix_export_status: xuất nền, không sửa dự án.
- mendix_list_units: tìm theo tên, phân trang; lấy ID để đọc.
- mendix_read_unit: JSON chia thành đoạn <=1400 byte; tiếp tục bằng next_chunk.
- mendix_start_report / mendix_report_step / mendix_report_status:
  báo cáo Ollama có tiến độ, bằng chứng, metrics và kết quả phân trang.
- mendix_list_sources / mendix_read_source: đọc source Mendix riêng.

Unit types hỗ trợ: DomainModels$DomainModel, Microflows$Microflow,
Microflows$Nanoflow, Pages$Page, JavaActions$JavaAction,
JavaScriptActions$JavaScriptAction. Một số loại có thể không xuất hiện trong dự án.

HTTP cần repo:read để đọc; xuất cần thêm repo:run vì chạy mx.exe được cấu hình
bởi host; báo cáo cần thêm chat. Báo cáo tách theo identity. Snapshot mô hình
được chia sẻ giữa người có quyền đọc cùng repository. Stdio tin cậy process local.

## Tiến độ và giới hạn

Dữ liệu ở `.router-state/mendix` (hoặc dưới ROUTER_STATE_DIR). Chỉ mục SQLite
giữ từng unit; JSON lớn được xóa sau khi nhập. Giới hạn 256 MB/bản xuất,
10 bản xuất, 100 báo cáo, 500 đoạn/báo cáo. Archive dữ liệu cũ trên host khi đầy;
giữ snapshot của báo cáo cần tiếp tục. Không expose đường dẫn file tùy ý qua MCP.

Báo cáo tiếp tục được sau restart bằng report_id; bản xuất đang chạy khi restart
sẽ interrupted và phải tạo lại. Mỗi bước gọi Ollama một lần; khi bận hoặc lỗi,
retry_required giữ nguyên vị trí. Đầu ra bị cắt được gắn cảnh báo, không tự coi
là phân tích đầy đủ. So sánh size/mtime của .mpr và .mxunit phát hiện sửa đổi
thông thường; đây không phải xác minh hash nội dung chống thay đổi có chủ ý.

Các bước là nhận xét từng đoạn JSON, có thể thiếu quan hệ liên unit. Chưa có
kiểm tra build Mendix và chưa có sửa MPR/microflow/page. Có thể dùng source
đã đọc làm ngữ cảnh để đề xuất Java/JS, rồi kiểm tra với Studio Pro trước khi dùng.

## Kiểm thử

```powershell
cd D:\MCP-Ollama-Router
.\.venv-31210\Scripts\python.exe -m pytest -o addopts= -q tests/test_mendix.py tests/test_mendix_http.py
.\.venv-31210\Scripts\python.exe -m scripts.test_mendix_mcp --output .router-state/mendix-smoke-report.md
```

Smoke test dùng router state tạm riêng, chỉ đọc dự án thật; xuất AMS và gọi
Ollama thật cho một microflow nhỏ. Cần Ollama đang chạy. State/report ID của
smoke test bị xóa khi kết thúc; file báo cáo --output được giữ lại.
