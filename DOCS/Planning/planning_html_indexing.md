---
title: "Kế hoạch đọc và index HTML v1"
version: v1
status: PLAN_DRAFT
workflow: /pl
created: 2026-09-01
wsrcore_repository: https://github.com/ThayDuke/WSRCore
wsrcore_commit: b12aab2a2bbc0ac27db2d74d608a96cab3a0eff1
---

# Kế hoạch đọc và index HTML v1

## 1. Mục tiêu

Cho phép SuperSearch phát hiện, đọc, chuẩn hóa và index nội dung hiển thị của tệp `.html` và `.htm`.

Kết quả phải tìm kiếm được qua SQLite FTS5, Quick View, bộ lọc định dạng và thống kê hiện có.

## 2. Hiện trạng đã xác minh

- Scanner chỉ nhận PDF, Office, ảnh và Markdown; `.html` và `.htm` chưa nằm trong allowlist.
- MarkItDown 0.1.6 đã có `HtmlConverter`, nhận cả `.html` và `.htm`.
- Converter dùng BeautifulSoup, bỏ `script` và `style`, rồi chuyển phần `body` sang Markdown.
- Converter có fallback văn bản thuần cho HTML lồng quá sâu.
- Pipeline cache Markdown, SQLite FTS5 và bộ lọc extension đang dùng metadata chung.
- Không cần đổi schema SQLite, API tìm kiếm hoặc JavaScript giao diện.
- GitNexus chưa index repository này; phân tích ảnh hưởng dùng source, diff và kiểm thử cục bộ.

## 3. Phạm vi

### Trong phạm vi

- Thêm `.html` và `.htm` vào định dạng quét.
- Dùng `HtmlConverter` sẵn có của MarkItDown; không tạo converter trùng chức năng.
- Ghi cache Markdown cùng header nguồn, `scan_id`, chữ ký file và đường dẫn gốc hiện tại.
- Index tiêu đề, heading, đoạn văn, danh sách, bảng và văn bản liên kết hiển thị.
- Loại nội dung `script` và `style` khỏi index.
- Hiển thị HTML/HTM trong thống kê và bộ lọc extension hiện tại.
- Bổ sung kiểm thử hồi quy, tài liệu sử dụng, build EXE và portable package.

### Ngoài phạm vi

- Không thực thi JavaScript.
- Không tải URL, ảnh, stylesheet, iframe hoặc tài nguyên mạng.
- Không crawl các liên kết trong HTML.
- Không render DOM bằng trình duyệt để lấy nội dung sinh động.
- Không index CSS, mã JavaScript hoặc dữ liệu nhị phân nhúng.
- Không thay đổi thuật toán xếp hạng FTS5.

## 4. Thiết kế triển khai

Luồng dự kiến:

1. `os.walk` phát hiện `.html` và `.htm` trong thư mục được chọn.
2. Cơ chế stale-check quyết định dùng cache hay chuyển đổi lại.
3. MarkItDown `HtmlConverter` đọc local file và loại `script` cùng `style`.
4. Nội dung hiển thị được chuẩn hóa thành Markdown trong runtime cache.
5. Pipeline phân loại hiện tại tạo metadata và `content_clean`.
6. `IndexStore.replace_entries` cập nhật SQLite và FTS5 theo giao dịch.
7. Giao diện nhận tổng số, extension và kết quả qua API hiện tại.

Quyết định kỹ thuật:

- Mở rộng `supported_extensions` tại một điểm duy nhất trong `scan_and_index`.
- Ghi rõ `.html` và `.htm` là `formal_document` trong phân loại nguồn.
- Không thêm dependency vì BeautifulSoup đã được MarkItDown sử dụng và đóng gói.
- Giữ nguyên bảo vệ không xóa index cũ khi hậu xử lý tạo index rỗng bất thường.
- Giữ nội dung HTML hoàn toàn offline và không thực thi mã nhúng.

## 5. Ảnh hưởng dự kiến

### Backend

- `src/app.py`: allowlist định dạng và phân loại nguồn.
- Không thay đổi cấu trúc `db_entries` hoặc API public.

### Lưu trữ

- `runtime/MARKDOWN/<scan_id>` có thêm cache từ HTML/HTM.
- `runtime/supersearch.db` nhận extension HTML/HTM qua trường đường dẫn hiện có.
- Không migration schema.

### Giao diện

- Bộ lọc extension tự nhận `HTML` và `HTM` từ `get_index_stats`.
- Quick View dùng nội dung Markdown đã chuẩn hóa như các tài liệu khác.
- Không cần chỉnh logic tìm kiếm phía trình duyệt.

### Build và đóng gói

- Không thêm asset hoặc thư viện mới vào EXE.
- Kích thước EXE dự kiến chỉ thay đổi không đáng kể.
- Build incremental và external UI giữ nguyên.

### Tài liệu

- Cập nhật `readme.txt` và `Readme.html` về HTML/HTM.
- Nêu rõ chỉ index nội dung hiển thị, không chạy JavaScript và không crawl mạng.

## 6. Các bước và gate

### Bước 1 — Neo hồi quy

- Chạy toàn bộ kiểm thử hiện có.
- Ghi nhận tổng index mẫu hiện tại và kích thước EXE.

Gate 1:

- Kiểm thử hiện có đạt.
- Không có thay đổi ngoài phạm vi chưa được giải thích.

### Bước 2 — Mở rộng backend

- Thêm `.html` và `.htm` vào allowlist quét.
- Ghi rõ hai extension trong phân loại nguồn.
- Không đăng ký converter mới.

Gate 2:

- HTML được chuyển thành Markdown.
- Script và style không xuất hiện trong Markdown hoặc SQLite.
- Không có request mạng trong quá trình chuyển đổi.

### Bước 3 — Kiểm thử tích hợp

- Thêm fixture HTML UTF-8 có title, heading, đoạn văn, bảng, link, script và style.
- Thêm fixture `.htm` để kiểm tra extension thứ hai.
- Quét thư mục nằm dưới đường dẫn có `build_artifacts`.
- Xác minh tổng tài liệu, FTS, extension stats, đường dẫn gốc và Quick View payload.
- Sửa nội dung HTML rồi quét lại để kiểm tra stale cache và không trùng bản ghi.
- Thêm HTML rỗng hoặc chỉ có script để xác minh bảo vệ index cũ.

Gate 3:

- Tìm thấy nội dung hiển thị.
- Không tìm thấy chuỗi chỉ nằm trong script hoặc style.
- Quét lại không tạo bản ghi trùng.
- HTML lỗi không làm mất index hợp lệ trước đó.

### Bước 4 — Tài liệu và UX

- Cập nhật danh sách định dạng hỗ trợ.
- Mô tả giới hạn local-only, không JavaScript và không crawl.
- Xác minh bộ lọc HTML/HTM xuất hiện tự động.

Gate 4:

- Tài liệu khớp hành vi thực tế.
- Không cần thay đổi giao diện hoặc API ngoài dự kiến.

### Bước 5 — Build và đóng gói

- Chạy `py_compile` và toàn bộ `unittest`.
- Build cưỡng chế EXE một lần.
- Kiểm tra kích thước và archive không nhúng lại HTML UI hoặc Tesseract.
- Tạo portable ZIP và kiểm tra manifest.
- Smoke test quét HTML bằng bản build.

Gate 5:

- EXE khởi động bình thường.
- HTML/HTM được index và tìm kiếm trong bản build.
- Portable ZIP chứa đúng EXE mới và Tesseract ngoài.

## 7. Ma trận kiểm thử tối thiểu

| Trường hợp | Kết quả bắt buộc |
| --- | --- |
| HTML UTF-8 | Index title và nội dung body |
| HTM UTF-8 | Hoạt động như HTML |
| Script và style | Không xuất hiện trong FTS |
| Bảng và danh sách | Nội dung chữ vẫn tìm được |
| Link nội bộ và ngoài | Chỉ index nhãn hiển thị, không tải URL |
| HTML malformed | Chuyển đổi an toàn hoặc báo lỗi file |
| HTML lồng sâu | Dùng fallback văn bản thuần |
| HTML rỗng | Không xóa index cũ |
| Sửa HTML | Cache được làm mới |
| Quét lại | Không trùng tài liệu |
| Extension stats | Có HTML và HTM đúng số lượng |
| Build artifacts path | Không bị bộ lọc đường dẫn loại nhầm |

## 8. Rủi ro và giảm thiểu

- HTML rất lớn có thể tăng RAM: giữ worker động và kiểm thử file lớn đại diện.
- Encoding lạ có thể sai dấu: kiểm thử UTF-8 và một mẫu legacy có khai báo charset.
- Trang chứa nhiều navigation có thể gây nhiễu: dùng body text theo converter hiện có.
- HTML chỉ sinh nội dung bằng JavaScript sẽ rỗng: ghi rõ giới hạn, không thực thi JavaScript.
- Thay đổi allowlist có thể quét UI ứng dụng: managed source directories hiện phải tiếp tục được loại đúng.
- Lỗi converter có thể làm index rỗng: giữ gate bảo vệ index cũ và báo lỗi rõ.

Mức rủi ro tổng thể: THẤP đến TRUNG BÌNH.

## 9. Tiêu chí hoàn tất

- `.html` và `.htm` được phát hiện khi quét.
- Nội dung hiển thị được lưu Markdown và index FTS5.
- Script, style và tài nguyên mạng không được xử lý hoặc thực thi.
- Tìm kiếm, bộ lọc, Quick View và thống kê hoạt động với HTML/HTM.
- Quét lại giữ tính incremental và không trùng bản ghi.
- Index cũ được bảo vệ khi chuyển đổi HTML thất bại bất thường.
- Kiểm thử tự động, build EXE và portable packaging đều đạt.
- Tài liệu phản ánh đúng định dạng và giới hạn hỗ trợ.

## 10. Rollback

- Gỡ `.html` và `.htm` khỏi allowlist.
- Gỡ khai báo phân loại HTML/HTM.
- Gỡ kiểm thử và tài liệu riêng cho HTML.
- Quét lại để pipeline dọn cache HTML mồ côi sau khi index hợp lệ commit.
- Không cần rollback schema hoặc migration dữ liệu.

## 11. Điều kiện triển khai

Kế hoạch này không cấp quyền sửa source.

Chỉ triển khai sau tín hiệu phê duyệt allowlist chính xác của WSRCore.

## 12. Kết quả triển khai sau phê duyệt

- Đã thêm `.html` và `.htm` vào allowlist quét và nhóm `formal_document`.
- Đã bổ sung kiểm thử UTF-8 cho HTML/HTM, nội dung hiển thị, bảng, danh sách và loại bỏ script.
- Đã cập nhật `readme.txt` và `Readme.html` về định dạng cùng giới hạn local-only.
- `python -m unittest discover -s tests -p "test_*.py" -v`: 3/3 kiểm thử đạt.
- Đã build lại `build_artifacts/SuperSearch.exe` và đóng gói `SuperSearch_Portable.zip`.
- Build lặp khi không đổi đầu vào được bỏ qua trong khoảng 60 ms.
