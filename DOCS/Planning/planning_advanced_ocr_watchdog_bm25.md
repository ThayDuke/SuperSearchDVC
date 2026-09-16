---
title: "Kế hoạch Tích hợp Năng Lực Nâng Cao: Safe Chunking, Quota Manager, Xuất DOCX, KaTeX Offline, Folder Watchdog, Trọng số BM25"
version: v1
status: completed
task: advanced_ocr_watchdog_bm25
created: 2026-09-12
updated: 2026-09-12
author: Antigravity
---

# Kế Hoạch Triển Khai Năng Lực Nâng Cao SuperSearch (v1)

## 1. Mục tiêu (Objective)
Tích hợp 6 năng lực nâng cấp thực chiến lấy cảm hứng từ D-OCR (Looking-Back-OCR), Everything và Paperless-ngx nhằm đưa SuperSearch đạt mức độ tin cậy, tự động hóa và trải nghiệm tra cứu tối ưu:
1. **Safe Chunking**: Chia nhỏ và giải phóng bộ nhớ khi xử lý PDF dung lượng lớn, chặn đứng lỗi tràn RAM OOM.
2. **Quota Manager**: Tự động lùi nhịp lũy thừa (Exponential Backoff + Jitter) khi gặp HTTP 429 từ Gemini API, bảo vệ tiến trình quét không gián đoạn và tự động chuyển đổi sang Tesseract cục bộ khi cạn ngạch.
3. **Bộ Xuất Kết Quả (DOCX & Markdown)**: Hỗ trợ xuất tài liệu bóc tách sang `.docx` (tận dụng `python-docx` sẵn có) và `.md` chuẩn hóa với đầy đủ định dạng bảng biểu và công thức toán.
4. **KaTeX Cục Bộ (100% Offline)**: Đóng gói thư viện KaTeX nội bộ, loại bỏ hoàn toàn CDN MathJax, đảm bảo dựng công thức toán tức thì và bảo mật tuyệt đối trong môi trường không kết nối Internet.
5. **Folder Watchdog (Auto-Index)**: Lắng nghe thay đổi thư mục thời gian thực (tạo, sửa, xóa tệp) trên nền Windows (ReadDirectoryChangesW / luồng giám sát), tự động kích hoạt cập nhật gia tăng (Incremental Sync) mà không cần quét lại thủ công.
6. **Trọng số BM25 Đa Tầng**: Nâng cấp lược đồ FTS5 với trường tiêu đề mục (`headings_clean`), tinh chỉnh trọng số BM25 ưu tiên tên tệp / tiêu đề chính (10.0), tiêu đề mục (5.0) và thân bài (1.0).

---

## 2. Phạm Vi & Chi Tiết Kỹ Thuật (Scope & Technical Design)

### 2.1. Safe Chunking cho PDF Lớn (Chống Tràn RAM)
- **Vấn đề**: Các file PDF scan hàng trăm trang khi mở toàn bộ bằng `pdfplumber` sẽ tích tụ đối tượng đồ họa và bộ đệm ảnh trong RAM, dẫn tới suy sụp ứng dụng.
- **Giải pháp**:
  - Thiết lập cơ chế phân trang theo lô (Chunk-based batching, mặc định 10-15 trang/chunk).
  - Khởi tạo tiến trình quét đọc theo block: xử lý xong block nào, ép buộc xả bộ nhớ trang, đóng buffer ảnh và gọi `gc.collect()`.
  - Ghi tạm nội dung Markdown từng block vào tệp staging tạm trên đĩa thay vì dồn mảng ký tự khổng lồ trên RAM.

### 2.2. Quota Manager & Exponential Backoff cho Gemini OCR
- **Vấn đề**: Gemini API miễn phí hoặc trả phí đều có giới hạn RPM/TPM và RPD. Khi gặp lỗi 429 (Too Many Requests), mã nguồn hiện tại ném ngoại lệ làm hỏng task quét.
- **Giải pháp**:
  - Xây dựng lớp `GeminiQuotaManager` với thuật toán Exponential Backoff + Jitter:
    - Lần 1: Chờ $2^1 + \text{rand}(0, 1)$ giây (2 - 3s).
    - Lần 2: Chờ $2^2 + \text{rand}(0, 1)$ giây (4 - 5s).
    - Lần 3: Chờ $2^3 + \text{rand}(0, 1)$ giây (8 - 9s).
    - Tối đa 4 lần thử lại.
  - Phân loại lỗi: Nếu lỗi 429 tạm thời (Rate Limit) -> lùi nhịp tự động. Nếu cạn kiệt hạn ngạch ngày (Quota Exhausted) -> chuyển tiếp mềm (graceful fallback) sang bộ máy Tesseract cục bộ, gắn nhãn trạng thái tài liệu để người dùng biết.
  - Pacing điều tiết: Thiết lập khoảng nghỉ an toàn tối thiểu giữa các lệnh gọi liên tiếp (mặc định 1.5s - 2s/call).

### 2.3. Xuất Tài Liệu Chuẩn Hóa (DOCX & Markdown)
- **Vấn đề**: Người dùng sau khi tra cứu và xem trước tài liệu OCR thường có nhu cầu biên tập lại nội dung trong Word hoặc tích hợp vào hệ thống ghi chú cá nhân (Obsidian, Notion).
- **Giải pháp**:
  - Bổ sung module `src/services/export_service.py`:
    - `export_to_markdown(document_id, output_path)`: Xuất file Markdown sạch kèm frontmatter metadata chuẩn.
    - `export_to_docx(document_id, output_path)`: Sử dụng thư viện `python-docx` đã cài sẵn, chuyển đổi tiêu đề Heading 1-3, đoạn văn, danh sách đạn, khối trích dẫn và bảng biểu thành các phần tử Word gốc.
  - Thêm phương thức API trong `Api` class: `export_document(document_id, format_type)`.
  - Bổ sung nút bấm trực quan trên thanh công cụ xem trước (Preview Toolbar): "Xuất Word (.docx)" và "Xuất Markdown (.md)" có hộp thoại lưu file (File Save Dialog).

### 2.4. KaTeX Cục Bộ (100% Offline Math Rendering)
- **Vấn đề**: Thư viện MathJax tải từ `cdn.jsdelivr.net` khiến ứng dụng không thể hiển thị công thức toán khi ngắt mạng hoặc trong mạng nội bộ cô lập.
- **Giải pháp**:
  - Tải và nhúng trực tiếp bộ thư viện KaTeX độc lập (katex.min.js, katex.min.css, bộ webfonts woff2) vào thư mục `data/vendor/katex/`.
  - Cập nhật `src/html_builder.py` và `data/SuperSearch.html` để tải tài nguyên KaTeX từ đường dẫn cục bộ `assets/katex/`.
  - Render công thức toán học dạng inline `$ ... $` hoặc block `$$ ... $$` ngay khi tài liệu hiển thị mà không phụ thuộc bất kỳ kết nối mạng nào.

### 2.5. Folder Watchdog (Tự Động Bắt Sự Kiện File Đổi Để Lập Chỉ Mục)
- **Vấn đề**: Hiện tại người dùng phải bấm nút "Quét lại" thủ công để nhận biết các tệp vừa thêm, sửa hoặc xóa.
- **Giải pháp**:
  - Xây dựng dịch vụ nền `FolderWatchdogService` trong `src/services/folder_watchdog.py`:
    - Tận dụng cơ chế bắt sự kiện tệp gốc của Windows thông qua `ctypes` (`ReadDirectoryChangesW`) hoặc polling nhẹ nhàng theo mtime thư mục nếu không khả dụng, không cài đặt thêm dependency nặng.
    - Bộ đệm trì hoãn (Debounce Buffer, ví dụ 3-5 giây): gom nhóm nhiều sự kiện ghi file liên tiếp để tránh quét trùng lặp khi file đang được ghi dở dang.
    - Tự động gọi `sync_entries` của `IndexStore` để cập nhật chỉ mục gia tăng trong tích tắc (dưới 1 giây).
  - Có công tắc bật/tắt (Toggle) trong giao diện Cài đặt để người dùng chủ động kiểm soát.

### 2.6. Trọng Số BM25 Đa Tầng (Ưu Tiên Tên Tệp và Tiêu Đề Mục)
- **Vấn đề**: Hiện tại FTS5 chỉ lập chỉ mục 2 trường chung: `title_clean` và `content_clean`. Khi từ khóa xuất hiện nhiều lần trong thân bài nhưng không liên quan đến tiêu đề mục chính, kết quả có thể bị đẩy lên trước tài liệu có từ khóa nằm ngay ở tiêu đề mục.
- **Giải pháp**:
  - Mở rộng cấu trúc bảng `documents`: bổ sung trường `headings_clean` (tập hợp tất cả các dòng tiêu đề H1-H4 được bóc tách từ Markdown hoặc tài liệu).
  - Nâng cấp bảng ảo FTS5:
    `CREATE VIRTUAL TABLE documents_fts USING fts5(title_clean, headings_clean, content_clean, tokenize='unicode61 remove_diacritics 2');`
  - Cấu hình trọng số BM25 đa tầng:
    `bm25(documents_fts, 10.0, 5.0, 1.0)`
    - Trọng số 10.0 cho `title_clean` (Tên tệp và tiêu đề tài liệu).
    - Trọng số 5.0 cho `headings_clean` (Tiêu đề các phần, chương, mục lớn).
    - Trọng số 1.0 cho `content_clean` (Nội dung chi tiết trong bài).
  - Tự động di trú dữ liệu (Migration) an toàn từ schema cũ mà không làm mất chỉ mục hiện hữu.

---

## 3. Rủi Ro & Giải Pháp Phòng Ngừa (Risks & Mitigations)
1. **Rủi ro khóa file trên Windows khi Watchdog kích hoạt**:
   - Khi một file Office hoặc PDF đang được tải xuống hoặc đang lưu dở, việc bóc tách ngay có thể bị lỗi Permission Denied / File Locked.
   - *Phòng ngừa*: Thử kiểm tra quyền mở đọc (`try open file with shared read`) với cơ chế retry 3 lần kèm debounce 3 giây trước khi nạp vào bộ chuyển đổi.
2. **Rủi ro tương thích lược đồ FTS5**:
   - Việc thêm cột vào FTS5 yêu cầu cập nhật triggers và rebuild lại bảng ảo FTS5.
   - *Phòng ngừa*: Tự động phát hiện phiên bản schema trong `index_metadata`, thực hiện migration mượt mà và rebuild FTS5 trong nền mà không khóa giao diện người dùng.
3. **Rủi ro xung đột luồng khi xuất file DOCX**:
   - *Phòng ngừa*: Thực hiện chuyển đổi và ghi file trên luồng Worker độc lập, báo trạng thái hoàn tất về GUI qua callback.

---

## 4. Các Bước Triển Khai Chi Tiết (Step-by-Step Implementation Steps)

### Bước 1: Quota Manager & Safe Chunking
- [x] Bổ sung `GeminiQuotaManager` vào `src/gemini_ocr_engine.py` với exponential backoff, pacing delay và fallback Tesseract.
- [x] Nâng cấp `LocalOcrPdfConverter` trong `src/app.py` xử lý PDF theo batch chunk 10 trang kèm xả đệm RAM.

### Bước 2: Tích hợp KaTeX Cục Bộ
- [x] Đưa tài nguyên KaTeX (CSS, JS, Fonts) vào `data/vendor/katex/`.
- [x] Điều chỉnh `src/html_builder.py` và `data/SuperSearch.html` nạp KaTeX cục bộ, gỡ MathJax CDN.

### Bước 3: Nâng cấp Lược đồ FTS5 & Trọng số BM25
- [x] Cập nhật `src/index_store.py`: thêm trường `headings_clean` vào bảng `documents` và `documents_fts`.
- [x] Cập nhật câu lệnh xếp hạng FTS5 sang `bm25(documents_fts, 10.0, 5.0, 1.0)`.
- [x] Tích hợp trích xuất tiêu đề mục tự động trong quá trình lập chỉ mục.

### Bước 4: Xây dựng Bộ Xuất File (DOCX & Markdown)
- [x] Tạo module `src/export_service.py` xử lý chuyển đổi Markdown sang `.docx` (dùng `python-docx`) và `.md`.
- [x] Thêm API `export_document` trong `Api` class và thêm nút bấm xuất file trên giao diện preview.

### Bước 5: Xây dựng Dịch Vụ Nền Folder Watchdog
- [x] Tạo `src/folder_watchdog.py` theo dõi thư mục quét hiện tại trên Windows với debounce buffer.
- [x] Kết nối sự kiện Watchdog với phương thức `sync_entries` của `IndexStore`.
- [x] Bổ sung phương thức điều khiển Watchdog (`enable_watchdog`, `disable_watchdog`, `get_watchdog_status`) trong `Api`.

### Bước 6: Kiểm Thử & Nghiệm Thu
- [x] Viết unit tests kiểm tra Quota Manager, Safe Chunking, BM25 ranking, KaTeX offline và Export DOCX.
- [x] Chạy kiểm thử tự động toàn dự án (37/37 tests PASS), xác nhận không có lỗi hồi quy.

---

## 5. Tiêu Chí Nghiệm Thu (Acceptance Criteria)
1. **Chống tràn RAM**: Quét tệp PDF scan 200+ trang không để bộ nhớ RAM vượt quá 350MB trong suốt chu kỳ.
2. **Kháng lỗi 429**: Mô phỏng lỗi HTTP 429, hệ thống tự động lùi nhịp lũy thừa và hoàn tất hoặc fallback an toàn sang Tesseract mà không văng lỗi.
3. **Tra cứu chuẩn xác**: Các truy vấn khớp tiêu đề mục hoặc tên tệp được xếp hạng ưu tiên rõ rệt trước kết quả chỉ khớp ngẫu nhiên trong thân bài.
4. **Offline 100%**: Ngắt kết nối mạng hoàn toàn, công thức toán trong tài liệu vẫn hiển thị sắc nét tức thì qua KaTeX.
5. **Xuất file chuẩn**: Tệp DOCX xuất ra mở tốt trong Microsoft Word với đầy đủ heading, bảng biểu và văn bản bóc tách.
6. **Tự động đồng bộ**: Khi thêm hoặc sửa tệp trong thư mục quét, Watchdog tự nhận diện và cập nhật chỉ mục trong vòng 5 giây mà không cần thao tác tay.

---

## 6. Điều Kiện Chặn & Phê Duyệt (Gate & Approval)
- Đây là kế hoạch lập trình chi tiết (Plan Draft).
- Tuyệt đối không chỉnh sửa mã nguồn cho đến khi nhận được phê duyệt chính thức từ người dùng.
- Lệnh phê duyệt hợp lệ: `ok`, `làm đi`, `duyệt`, `ok duyệt`, `ok làm đi`, `được rồi làm đi`, `duyệt phương án`, `làm đi bạn`.
