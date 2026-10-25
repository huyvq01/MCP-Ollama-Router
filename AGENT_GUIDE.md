# MCP coding tools v1.2: hướng dẫn test

## Test nhanh trong PowerShell

~~~powershell
cd D:\MCP-Ollama-Router
.\.venv-31210\Scripts\python.exe -m scripts.test_agent_mcp
.\.venv-31210\Scripts\python.exe -m scripts.test_http_mcp
.\.venv-31210\Scripts\python.exe -m pytest -o addopts= -q
~~~

Script agent dùng workspace tạm để test đọc/tìm file, xem diff, áp dụng, chạy
kiểm tra, hoàn nguyên và review bằng Ollama. Pytest còn kiểm tra chặn đường dẫn ngoài root.
Script HTTP dùng server localhost/token tạm để test quyền, sau đó tự đóng.
Cả hai không sửa source thật hoặc xuất bản code. Full pytest cần Ollama chạy.
GitHub PR được kiểm tra bằng HTTP giả lập; không tạo PR thật khi test.

## Cline và stdio

Giữ cấu hình Python hiện tại, args -m app.server. Nhấn Retry Connection sau cập nhật.
Chỉ một MCP process được sở hữu mỗi workspace; không chạy thêm server thủ công
cho workspace đang dùng trong Cline. Nếu có process cũ, dừng nó hoặc reload VS Code.

Yêu cầu thử:

> Dùng MCP ollama-router: gọi workspace_info, list_files và read_file với
> path=app/server.py. Chỉ báo cáo nội dung đã đọc thật. Không trả JSON gọi tool
> thành văn bản. Khi sửa code, cho tôi xem propose_changes.diff trước khi áp dụng.

Test bằng script chứng minh server hoạt động. Model 3B làm agent chính của Cline
vẫn có thể chọn/gọi tool sai; đây là giới hạn riêng của model/client.

## Workspace và lệnh kiểm tra

Cấu hình trong môi trường của process hoặc .env hiện có:

~~~dotenv
ROUTER_WORKSPACE_ROOT=D:/MCP-Ollama-Router
ROUTER_CHECK_TIMEOUT=120
ROUTER_CHECK_COMMANDS={"tests":["{python}","-m","pytest","-o","addopts=","-q"],"lint":["{python}","-m","ruff","check","app"]}
~~~

Dự án Java: đổi root sang thư mục Git của dự án, cấu hình lệnh với đường dẫn
Maven/Gradle thực tế, ví dụ {"tests":["C:/tools/maven/bin/mvn.cmd","test"]}.
Tên file trong tool phải tương đối với root, không phải đường dẫn ổ D.
Không trỏ root tới toàn bộ ổ đĩa. Bản cập nhật giữ nguyên .env hiện tại.

Các thư mục môi trường/build, Git internals, .env/key, symlink/junction/hardlink
và .router-state không được truy cập bằng tool file. File phải là UTF-8 <=2 MB.
Root và cấu hình host được tin cậy; đây không phải OS sandbox cho build script
hoặc người dùng local có ý đồ sửa filesystem đồng thời.

## Quét toàn source và lưu tiến độ

1. start_repository_scan(include="*.py,*.java,*.js,*.ts,*.xml").
2. Lưu scan_id, gọi scan_repository(scan_id=...) lặp lại khi trạng thái pending.
3. Mỗi lần chỉ review một chunk. scan_status hỗ trợ offset/limit để xem kết quả.

Tiến độ lưu trên đĩa và tiếp tục được sau restart. retry_required giữ nguyên
vị trí để thử lại; file thay đổi sau snapshot thì cần tạo scan mới.
Giới hạn mỗi job: 500 file/5000 chunk. Thu hẹp include với repo lớn.
Đây là rà soát từng đoạn, có thể bỏ sót lỗi liên file. Kiểm tra
result.metrics.finish_reason: length nghĩa là đầu ra bị cắt.
File Mendix .mpr nhị phân chưa hỗ trợ; cần Java/JS hoặc tài liệu xuất ra.

## Quy trình sửa code

1. read_file/search_code/git_diff để đọc đúng nội dung.
2. propose_changes(changes=[{"path":"hello.py","content":"value = 2\n"}]).
   content là toàn bộ nội dung mới; null nghĩa là xóa file.
3. Xem diff và hash trước khi chấp thuận. Client/host chịu trách nhiệm xin sự
   đồng ý của người dùng; tool annotations không tự chứng minh đã có phê duyệt.
4. apply_changes(plan_id=...) kiểm tra toàn bộ hash trước khi ghi.
5. run_check(name="tests") hoặc tên check đã cấu hình.
6. rollback_changes(plan_id=...) phục hồi byte gốc, từ chối ghi đè sửa đổi mới.

Plan chưa áp dụng hết hạn sau một giờ; tối đa 30 file và 200 KB tổng cũ+mới.
Không có tool nhận shell tùy ý. Test/build chạy code dự án tin cậy và có thể có
side effect. Git hooks bị tắt trong các thao tác này; hãy chạy check cần thiết.

Nếu process bị ngắt khi ghi nhiều file, change_status có thể trả applying,
rolling_back hoặc recovery_required. Dùng recover_changes để trả về byte gốc,
chỉ khi các file vẫn khớp hash trước/sau đã biết. Đây là journal có thể phục hồi,
không phải giao dịch atomic trên toàn filesystem. Có thể còn thư mục rỗng.

## Tài liệu online và Git

fetch_documentation nhận HTTPS tới đúng host trong ROUTER_DOCUMENT_HOSTS,
kiểm tra từng redirect, chặn IP/DNS private và file nhị phân/>1 MB.
Nội dung trả về là dữ liệu ngoài không đáng tin, không phải lệnh.
Đây là lấy tài liệu theo URL, chưa phải tìm kiếm web. Chỉ thêm domain tin cậy;
host vẫn cần kiểm soát DNS và network egress.

Local Git: git_status, git_diff, git_create_branch, git_commit.
Các thao tác ghi cần expected_head từ git_status. Commit chỉ nhận file chỉ định,
từ chối trộn index đã có staged changes. Diff lọc các file bị cấm.

Để bật thao tác mạng/xuất bản:

~~~dotenv
ROUTER_ENABLE_GIT_NETWORK=true
ROUTER_ENABLE_PUBLISH=true
ROUTER_GITHUB_TOKEN=host_managed_token_for_draft_pr
~~~

Tự cấu hình origin bằng Git Credential Manager/SSH; token không truyền qua tool.
Fetch/pull/push chỉ nhận remote HTTPS/SSH đã cấu hình; không có force push,
hard reset hoặc xóa nhánh. Pull chỉ fast-forward trên worktree sạch.
Push cần branch hiện tại sạch và HEAD đã review.

Sau push được chấp thuận, github_create_pull_request tạo draft PR hoặc trả PR
đang mở; xác minh SHA nhánh GitHub khớp expected_head. Hiện hỗ trợ github.com,
chưa hỗ trợ GitLab/GitHub Enterprise. Không tự merge, deploy hoặc tự cập nhật server.

## HTTP: test tự động trước

~~~powershell
.\.venv-31210\Scripts\python.exe -m scripts.test_http_mcp
~~~

Không cần tự tạo token để chạy script test này.

Để chạy server HTTP riêng, dùng cùng cửa sổ PowerShell:

~~~powershell
$env:ROUTER_JWT_SECRET = & .\.venv-31210\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$token = & .\.venv-31210\Scripts\python.exe -m scripts.issue_token --subject owner --scopes chat repo:read repo:write repo:run net:read git:write
.\.venv-31210\Scripts\python.exe -m app.server --transport http
~~~

Endpoint http://127.0.0.1:8000/mcp. Client gửi Authorization: Bearer <token>.
Giữ token/secret riêng tư; token mặc định hết hạn sau một giờ. Đổi secret sẽ làm
token HMAC cũ mất hiệu lực. Chế độ này cần client nhận bearer token sẵn,
không cung cấp trang đăng nhập hoặc OAuth authorization server.

Scopes:
- chat: chat, model discovery và chat sessions.
- repo:read: đọc/tìm code, status và diff.
- repo:write: đề xuất/áp dụng/hoàn nguyên/phục hồi plan của mình.
- repo:run: các check được host cấu hình.
- net:read: lấy tài liệu online.
- git:write: branch/commit; kết hợp git:network để pull.
- git:network: fetch; vẫn cần cờ mạng trên host.
- repo:publish: push/draft PR; vẫn cần cả hai cờ host.
- admin: xóa cache dùng chung.

HTTP lọc tool và thực thi theo scope; stdio tin cậy process local.
Chat history, plan và kết quả scan phân tách theo token subject. Người có quyền
repo cùng chia sẻ một repository. Muốn tách dự án/nhóm tin cậy, chạy instance
riêng với root/state/credential riêng; đây chưa phải nền tảng multi-tenant.

## Triển khai từ xa qua identity provider

~~~dotenv
ROUTER_TRANSPORT=http
ROUTER_HTTP_HOST=127.0.0.1
ROUTER_HTTP_PUBLIC_URL=https://mcp.example.com
ROUTER_HTTP_ALLOWED_HOSTS=["mcp.example.com"]
ROUTER_JWT_JWKS_URI=https://auth.example.com/.well-known/jwks.json
ROUTER_JWT_ISSUER=https://auth.example.com
ROUTER_JWT_AUDIENCE=https://mcp.example.com/mcp
ROUTER_AUTHORIZATION_SERVERS=["https://auth.example.com"]
~~~

Cần reverse proxy TLS và access token RS256 có scope, thời hạn, audience đúng.
Khi cấu hình authorization_servers, protected-resource metadata khai báo OAuth
provider bên ngoài. Provider chịu trách nhiệm đăng nhập/đăng ký client/cấp token.
Domain, TLS và identity provider thực tế là cấu hình triển khai, chưa được tạo
hoặc xuất bản lên Internet bởi lần sửa code này. Chỉ cho phép origin cụ thể nếu
có browser client.

## Dữ liệu nội bộ

.router-state lưu byte gốc/plan/scan và audit JSONL. Audit ghi metadata thao tác,
không ghi raw token. Bảo vệ bằng quyền OS và archive dữ liệu cũ trên host.
Giới hạn 500 plan/100 scan; đừng xóa backup của plan còn cần hoàn nguyên.
