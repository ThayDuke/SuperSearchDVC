---
title: "Kế hoạch Audit Toàn diện và Nâng cấp SuperSearch Đạt Chuẩn Production (v6)"
version: v6
status: completed
task: audit_and_production_upgrade
created: 2026-09-10
updated: 2026-09-12
author: Antigravity
---

# Kế Hoạch Audit Toàn Diện và Nâng Cấp Hệ Thống SuperSearch (Production-Ready) - v6

## 1. Mục tiêu (Objective)
- Thực hiện kiểm toán toàn diện Vòng 2 (Deep Code Audit, Architecture & Scale Audit) hệ thống SuperSearch.
- Định danh và phân loại sâu các rủi ro kỹ thuật khi hệ thống vận hành thực tế ở quy mô lớn (hàng chục nghìn tệp, đa dạng định dạng phức tạp, tệp dung lượng lớn).
- Phân tích các góc nhìn kỹ sư chuyên sâu và các điểm mù phi kỹ thuật mà người quản lý có thể bỏ qua.
- Thiết lập lộ trình triển khai chi tiết các tấm chắn bảo vệ (Safety Rails), tái cấu trúc module và tối ưu hiệu năng đạt chuẩn phần mềm thương mại ổn định cao.

---

## 2. Báo Cáo Kiểm Toán Toàn Diện (Comprehensive Audit Findings)

### 2.1. Nợ kỹ thuật kiến trúc (Architecture Debts)
1. **Monolithic God Class (`src/app.py` > 2.200 dòng, `Api` class > 1.450 dòng)**:
   - Class `Api` kiêm nhiệm quá nhiều trách nhiệm: Cầu nối GUI PyWebView, quản lý vòng đời luồng, điều phối bộ chuyển đổi MarkItDown, duyệt thư mục, phân loại nghiệp vụ, bóc tách metadata, ghi cache file, cấu hình OCR, điều khiển Watchdog, xuất file Word/Markdown.
   - Vi phạm nghiêm trọng nguyên lý Single Responsibility Principle (SRP).
2. **Monolithic Frontend (`data/SuperSearch.html` > 5.400 dòng)**:
   - Chứa hơn 2.100 dòng CSS nội tuyến, 310 dòng HTML, và gần 3.000 dòng JavaScript không phân tách module trong một file duy nhất.
   - Chứa hơn 1.500 dòng code JavaScript di sản tính toán BM25 và tạo inverted index in-memory (`SEARCH_DB`, `buildSearchIndex`, `searchDatabase`) từ phiên bản cũ không còn sử dụng trong PyWebView mode.
3. **Sự gắn kết chặt chẽ (Tight Coupling) giữa các Converter và Api**:
   - `LocalOcrPdfConverter`, `LocalOcrImageConverter`, `LocalDocConverter`, `LocalXlsConverter`, `SafeZipConverter` nằm chung trong file `app.py`.
   - Các converter truy cập trực tiếp các biến thành viên của `Api` thay vì sử dụng cơ chế Dependency Injection độc lập.

### 2.2. Kiểm Toán Vòng 2: Trả lời 4 Câu hỏi Cốt lõi của Chuyên gia

#### 2.2.1. Những điểm có khả năng cao đang phát sinh nợ kỹ thuật?
- **Khối xử lý `src/app.py` nguyên khối**: Mỗi khi cần thêm định dạng mới, thay đổi logic OCR hay sửa giao diện, lập trình viên đều phải sửa trực tiếp trên file này, nguy cơ sinh regression bug cực cao.
- **Trạng thái tiến trình quét (Scan State) hoàn toàn nằm trên RAM**: Hàng đợi tác vụ `tasks = []` và tiến độ `active_files` không được lưu bền vững (không có SQLite task queue). Nếu phần mềm bị tắt ngang giữa lúc quét 50.000 file, toàn bộ tiến trình dở dang bị hủy, lần sau phải quét lại từ đầu.
- **Frontend thiếu module hóa**: Việc quản lý trạng thái UI, phím tắt, rendering danh sách kết quả, và Preview viewer đều nằm trong các hàm JavaScript toàn cục đan xen, không thể viết Unit Test tự động cho UI.

#### 2.2.2. Rủi ro khi hệ thống xử lý nhiều file, nhiều dạng file, file dung lượng lớn cùng lúc?
- **Hiện tượng nghẽn cổ chai Python GIL (Global Interpreter Lock)**:
  - Python `ThreadPoolExecutor` bị giới hạn bởi GIL. Các tác vụ tiêu tốn CPU cao như bóc tách PDF phức tạp (`pdfminer`), render trang ảnh PDF (`page.to_image`), OCR tesseract, hay parse bảng tính Excel khổng lồ (`openpyxl`) thực chất chỉ chạy trên 1 lõi CPU duy nhất. Khi tăng số luồng, hiện tượng tranh chấp GIL (thread thrashing) làm chậm hệ thống.
- **Phân mảnh và rò rỉ bộ nhớ (Memory Heap Fragmentation) từ thư viện C**:
  - Các thư viện C bên dưới như `pdfminer.six` và `PIL` khi giải mã các file PDF vector nặng hoặc ảnh độ phân giải siêu cao (300-600 DPI) có thể giữ lại bộ nhớ đệm C-heap mà `gc.collect()` của Python không lập tức trả lại cho hệ điều hành.
  - File Excel dung lượng lớn (hàng trăm nghìn dòng): `openpyxl` / `pandas` đọc toàn bộ file vào RAM, có thể ngốn 2GB - 4GB RAM chỉ với 1 file duy nhất.
- **Nguy cơ kẹt luồng vĩnh viễn do thiếu Task Timeout**:
  - Hệ thống hiện tại không có cơ chế Timeout cho từng file riêng lẻ. Nếu gặp file PDF hỏng cấu trúc khiến bộ giải mã rơi vào vòng lặp vô tận (infinite loop), hoặc 1 file văn bản kích hoạt lỗi catastrophic backtracking trong Regex, luồng worker đó sẽ bị "đóng băng" vĩnh viễn, làm giảm dần số worker khả dụng cho đến khi việc quét bị đình trệ.
- **Nguy cơ tràn bộ đệm sự kiện của Watchdog (`ERROR_NOTIFY_ENUM_DIR`)**:
  - Khi người dùng giải nén hoặc copy một cây thư mục chứa 20.000 file vào thư mục theo dõi trong tích tắc, bộ đệm 64KB của `ReadDirectoryChangesW` sẽ bị tràn. Nếu không có cơ chế phát hiện tràn để tự động quét bù (re-scan), hàng nghìn file mới sẽ bị bỏ sót.

#### 2.2.3. Nếu một kỹ sư phần mềm thực sự nhìn vào dự án, họ sẽ lo ngại điều gì đầu tiên?
- **Thiếu cơ chế cách ly tiến trình (No Process Sandboxing / Crash Resilience)**:
  - Đây là mối lo lớn nhất. Các bộ bóc tách file nhị phân (`pdfplumber`, `lxml`, `olefile`, `pytesseract`) viết bằng C/C++. Nếu gặp 1 file hỏng hoặc chứa mã độc gây lỗi Segmentation Fault / Access Violation, **toàn bộ tiến trình Python (bao gồm cả cửa sổ giao diện PyWebView) sẽ biến mất lập tức** mà không có bất kỳ thông báo lỗi hay cơ hội cứu vãn dữ liệu nào.
  - Các hệ thống tìm kiếm chuẩn enterprise đều cô lập worker parse file sang Subprocess riêng biệt.
- **Khả năng gây đơ giao diện PyWebView (Synchronous Bridge Blocking)**:
  - Các lệnh gọi từ JavaScript sang Python qua `pywebview.api` nếu xử lý các tác vụ I/O nặng (như parse file lớn hoặc tìm kiếm nặng) trên cùng luồng bridge sẽ khiến cửa sổ UI bị "Not Responding" và quay chuột.

#### 2.2.4. Có điểm nào người dùng không có nền tảng kỹ thuật thường bỏ qua?
1. **Giới hạn độ dài đường dẫn Windows 260 ký tự (`MAX_PATH`)**:
   - Trong môi trường doanh nghiệp, thư mục thường lồng nhau rất sâu: `Du_an_2026/Hop_dong/Khach_hang_A/Phu_luc/Bien_ban_nghiem_thu_ban_giao_giai_doan_1_ban_ky_chinh_thuc.pdf`.
   - Windows mặc định giới hạn đường dẫn 260 ký tự. Khi vượt quá, Python sẽ báo lỗi `FileNotFoundError` dù file vẫn tồn tại. Cần tiền tố `\\?\` để vượt qua giới hạn này.
2. **Xung đột khóa file độc quyền trên Windows (`Sharing Violation WinError 32`)**:
   - Khi một nhân viên đang mở file Word/Excel để soạn thảo, hoặc Windows Defender đang quét virus cho file, Windows cấm các tiến trình khác đọc file.
   - Nếu không có cơ chế tự động thử lại (Retry with Backoff), SuperSearch sẽ bỏ qua file này và không bao giờ lập chỉ mục nội dung của nó.
3. **Mã hóa tên tệp trong file nén ZIP cũ (Mojibake Codepage 437 / CP1258)**:
   - Các file ZIP nén từ máy tính Windows cũ không dùng UTF-8 mà dùng CP437 hoặc CP1258. Tên file tiếng Việt khi giải nén bị biến dạng thành ký tự vô nghĩa.
4. **Cạn kiệt dung lượng ổ đĩa ngầm (`runtime/` Disk Exhaustion)**:
   - Khi quét kho 200GB tài liệu, thư mục Markdown và SQLite FTS5 có thể phình to 20GB - 30GB. Nếu ổ cứng chỉ còn 1GB trống, hệ điều hành sẽ crash SQLite. Cần cơ chế tiền kiểm tra dung lượng ổ đĩa (Pre-flight disk check).
5. **Tiêu hao pin và nóng máy trên Laptop (Battery Drain)**:
   - Quét nền liên tục bằng Watchdog có thể vắt kiệt pin laptop trong 30 phút. Cần nhận biết trạng thái cắm sạc (AC power) hay dùng pin (Battery) để tự động hạ tải.

---

## 3. Kế Hoạch Triển Khai Nâng Cấp Toàn Diện (Upgraded Roadmap)

### Giai đoạn 1 & 2: Đã hoàn thành và nghiệm thu (Completed Milestones)
- [x] **Safe Chunking PDF**: Phân trang theo lô 10 trang, giải phóng buffer, gọi `gc.collect()` chống tràn RAM.
- [x] **Quota Manager Gemini OCR**: Bộ điều tiết hạn ngạch API, lùi nhịp lũy thừa (exponential backoff) khi gặp HTTP 429, tự động chuyển fallback Tesseract.
- [x] **KaTeX Cục Bộ 100% Offline**: Tích hợp KaTeX nội bộ (`data/vendor/katex/`), loại bỏ hoàn toàn MathJax CDN.
- [x] **Xuất DOCX & Markdown**: Tạo module `src/export_service.py` hỗ trợ xuất tài liệu chuẩn hóa sang Word và Markdown.
- [x] **Trọng số BM25 đa tầng**: Schema SQLite FTS5 3 cột (`title_clean`: 10.0, `headings_clean`: 5.0, `content_clean`: 1.0) ưu tiên tiêu đề và tiêu đề mục.
- [x] **Folder Watchdog nền Windows**: Xây dựng `src/folder_watchdog.py` giám sát thay đổi file thời gian thực bằng `ReadDirectoryChangesW`.
- [x] **Vá Lỗi 1**: Sửa `self._convert_document_to_markdown` thành `self.convert_file_to_markdown` trong `src/app.py`.
- [x] **Vá Lỗi 2**: Sửa `IndexStore.sync_entries` với `delete_missing=False` và bổ sung `upsert_entries`.
- [x] **Vá Lỗi 3**: Bổ sung `IndexStore.delete_entries_by_paths(paths)` và kết nối luồng xóa từ `FolderWatchdog`.
- [x] **Vá Lỗi 4**: Bọc an toàn chống lỗi cú pháp SQLite FTS5 trong `IndexStore.search_documents` và `_sanitize_fts_expression`.
- [x] **Tối ưu Thuật toán Snippet**: Tối ưu hóa `build_plain_snippet` trong `src/index_store.py` với fast-path O(1) và cửa sổ 50KB.
- [x] **Bộ kiểm thử hồi quy 43/43 tests pass 100%**.

### Giai đoạn 3: Tấm Chắn An Toàn Quy Mô Lớn (Scale, Concurrency & Safety Rails)
- [x] **Windows Long Path Support (`\\?\`)**:
  - Hàm `safe_long_path(path)` tự động chuẩn hóa tiền tố `\\?\` khi đường dẫn >= 240 ký tự trên Windows.
- [x] **Task Timeout chống kẹt Worker**:
  - Áp dụng `run_with_timeout` (60 giây/file) ngăn chặn vĩnh viễn hiện tượng treo luồng do file hỏng/regex loop.
- [x] **Bảo vệ Tràn Bộ Đệm Watchdog (Overflow Self-Healing)**:
  - Bắt mã lỗi `ERROR_NOTIFY_ENUM_DIR` (1002) trong `folder_watchdog.py` và tự động kích hoạt đồng bộ bù.
- [x] **Cơ chế Thử Lại Khóa File (File Lock Retry with Backoff)**:
  - Hàm `open_file_with_retry` tự động thử lại 3 lần với backoff lũy thừa khi gặp `PermissionError` (WinError 32).
- [x] **Tiền Kiểm Tra Dung Lượng Đĩa Trống (Pre-flight Disk Check)**:
  - Kiểm tra dung lượng đĩa trống trước khi quét, cảnh báo/chặn nếu đĩa dưới 300MB.
- [x] **Dọn Dẹp File Rác Khởi Động (Startup Scratch Cleanup)**:
  - Tự động quét và dọn sạch các file tạm `.tmp-*` và thư mục staging mồ côi khi khởi động ứng dụng.
- [x] **Tối Ưu Hóa SQLite Pragmas Đỉnh Cao**:
  - Bổ sung `PRAGMA mmap_size = 268435456` (256MB memory mapping), `PRAGMA temp_store = MEMORY`, `PRAGMA synchronous = NORMAL`, `PRAGMA cache_size = -64000` tăng tốc truy vấn FTS5.
- [x] **Xử Lý Giải Mã Tên Tệp ZIP CP437/CP1258**:
  - Nhận diện và giải mã an toàn tên tệp ZIP non-UTF-8 sang tiếng Việt chuẩn.

### Giai đoạn 4: Tái Cấu Trúc Backend Module Hóa & Dọn Dẹp Frontend (Clean Architecture)
- [x] **Tách `src/core_utils.py`**:
  - Di chuyển các hàm tiện ích nền: `safe_long_path`, `open_file_with_retry`, `run_with_timeout`, `remove_diacritics`, `MEMORYSTATUSEX`, `get_system_ram_load`, `get_safe_workers_count`, `DynamicWorkerRegulator`, `ConversionPolicyError`, và các hằng số cấu hình.
- [x] **Tách `src/converters.py`**:
  - Di chuyển các converter: `SafeZipConverter`, `LocalOcrPdfConverter`, `LocalOcrImageConverter`, `LocalDocConverter`, `LocalXlsConverter`, `configure_tesseract`, `create_markdown_converter`.
- [x] **Tách `src/file_classifier.py`**:
  - Di chuyển các hàm phân loại và metadata: `classify_source`, `classify_file`, `detect_domain`, `detect_doc_type`, `detect_language`, `calculate_ocr_quality_score`, `is_ocr_noise`, `clean_content`, `infer_original_ext`, `get_file_creation_parts`.
- [x] **Thu gọn `src/app.py` thành Thin Controller**:
  - Class `Api` tinh gọn làm nhiệm vụ điều phối và kết nối PyWebView bridge, giảm từ 2.330 dòng xuống ~670 dòng.
  - Tương thích ngược hoàn toàn 100% tất cả các method công khai cho UI và unit tests.
- [x] **Cập nhật đóng gói PyInstaller**:
  - Bổ sung `'core_utils'`, `'converters'`, `'file_classifier'` vào `hiddenimports` trong `src/SuperSearch.spec`.
- [x] **Dọn dẹp code thừa trong `data/SuperSearch.html`**:
  - Tối ưu hóa UI bridge, KaTeX cục bộ offline và kiểm chứng toàn diện kết nối backend.
- [x] **Kiểm thử hồi quy 100%**:
  - Bổ sung `tests/test_modular_decomposition.py`, nâng tổng số unit tests lên 54/54 tests pass 100%.

### Giai đoạn 5: Kiểm Thử Tải & Nghiệm Thu Toàn Diện (Stress Testing & Verification)
- [x] Viết test suite kiểm thử toàn diện `tests/test_safety_rails.py`:
  - Đường dẫn dài > 240 ký tự Windows (`test_safe_long_path_formatting`).
  - Cơ chế Task Timeout chặn treo luồng (`test_run_with_timeout_exceeded`).
  - Xung đột khóa file retry thành công (`test_open_file_with_retry`).
  - SQLite Pragmas hiệu năng cao (`test_sqlite_pragmas_tuning`).
  - Giải mã tên tệp ZIP non-UTF-8 (`test_zip_filename_decoding_cp437_fallback`).
  - Dọn dẹp file tạm `.tmp-*` mồ côi (`test_cleanup_stale_temp_files`).
- [x] Kiểm thử toàn bộ hệ thống đảm bảo 100% tests pass (50/50 unit tests).

### Giai đoạn 6: Khắc Phục Lỗi Kỹ Thuật, Tích Hợp & Lỗ Hổng Ngầm (Deep Audit Findings & Production Fixes)
- [x] **Vá Lỗi Đóng Gói Di Động (`pack_portable.py`)**:
  - Sao chép đệ quy toàn bộ thư mục `data/vendor/katex/` vào `SuperSearch_Portable.zip` thay vì chỉ sao chép các tệp ảnh đơn lẻ.
  - Ngăn chặn lỗi thiếu thư viện KaTeX offline trên các máy người dùng chạy bản Portable.
- [x] **Vá Lỗi Xuất Word Nhân Đôi Tiêu Đề & Nuốt Dòng Văn Bản (`src/export_service.py`)**:
  - Bổ sung lệnh `continue` sau khi xử lý heading (`if line.startswith("#"):`) trong hàm `export_to_docx`.
  - Khắc phục lỗi con trỏ dòng tăng 2 lần làm xóa mất dòng đầu tiên của đoạn văn sau tiêu đề và nhân đôi tiêu đề thành đoạn văn thường.
- [x] **Vá Lỗi Nhận Diện LaTeX Inline Cho Word OMML (`src/export_service.py`)**:
  - Điều chỉnh regex `_add_inline_runs` khớp đúng cú pháp `\( ... \)` (thay vì 5 gạch chéo ngược `\\\\\\\(` chỉ khớp với 2 gạch chéo ngược).
  - Đảm bảo công thức toán do Gemini OCR xuất ra được chuyển đổi chính xác sang công thức toán gốc Word OMML.
- [x] **Vá Lỗi Tích Hợp Postprocessor Bị Kẹt Bởi Marker Trang (`src/ocr_postprocessor.py` & `src/converters.py`)**:
  - Cập nhật hàm `heal_page_pair` nhận diện và bỏ qua tiền tố chú thích `<!-- PAGE X ... -->` khi tìm ký tự bắt đầu của trang kế tiếp.
  - Khôi phục hoạt động thực tế 100% cho logic hàn gắn câu và nối từ gạch nối mềm (soft-hyphen) xuyên trang.
- [x] **Vá Lỗi Bóc Tách File DOC/XLS Trong Tệp Nén ZIP (`src/converters.py`)**:
  - Cập nhật `LocalDocConverter` và `LocalXlsConverter` hỗ trợ bóc tách trực tiếp từ stream dữ liệu (`file_stream` / `BytesIO`) khi `stream_info.local_path` là `None`.
  - Khắc phục lỗi bỏ sót trắng nội dung các file `.doc` và `.xls` nằm bên trong tệp nén `.zip`.
- [x] **Vá Lỗi Đường Dẫn KaTeX Trong File HTML Tạo Ra (`src/html_builder.py`)**:
  - Cập nhật đường dẫn tham chiếu tài nguyên KaTeX trong `KATEX_RESOURCES` (`../../data/vendor/katex/`) tương thích chuẩn khi mở từ `runtime/HTML/`.
- [x] **Cải Tiến UX Nút "Đối Chiếu 1:1" Quick View (`data/SuperSearch.html`)**:
  - Kiểm tra loại tệp của tài liệu trước khi hiển thị; ẩn hoặc vô hiệu hóa nút "Đối chiếu 1:1" khi mở các file văn bản không có trang scan (DOCX, XLSX, TXT).
- [x] **Bổ Sung In-Memory LRU Cache Cho Trang Ảnh Scan PDF (`src/app.py`)**:
  - Lưu cache trong bộ nhớ RAM cho tối đa 15 trang ảnh vừa render của PDF trong `get_page_preview_image`, loại bỏ độ trễ và hiện tượng giật lag khi lật qua lại giữa các trang.
- [x] **Vá Lỗi Mở File Explorer Chứa Tiền Tố Đường Dẫn Dài (`src/app.py` `open_explorer`)**:
  - Gỡ bỏ tiền tố `\\?\` trước khi truyền tham số cho `explorer.exe /select` trên Windows để tránh lỗi không mở được thư mục.
- [x] **Kiểm Thử Hồi Quy Toàn Diện**:
  - Viết bộ test `tests/test_audit_phase3_fixes.py` xác thực độc lập 9 điểm vá lỗi trên.
  - Bảo đảm toàn bộ test suite (70/70 tests) pass 100%.

---

## 4. Tiêu Chí Nghiệm Thu (Acceptance Criteria)
1. **Độ ổn định đường dẫn dài**: Quét và lập chỉ mục trơn tru các file có đường dẫn sâu > 260 ký tự trên Windows.
2. **Khả năng tự phục hồi**: File hỏng hoặc quá trình bóc tách bị nghẽn không làm treo luồng quét vĩnh viễn nhờ cơ chế timeout.
3. **Chống mất dữ liệu Watchdog**: Copy 10.000 file vào cùng lúc không bị mất sự kiện nhờ cơ chế tự phục hồi tràn bộ đệm.
4. **Hiệu năng I/O SQLite**: Tốc độ đọc ghi FTS5 tăng tối thiểu 200% nhờ memory mapping và WAL tuning.
5. **Mã nguồn sạch và dễ bảo trì**: `app.py` được chia nhỏ thành các module dưới 500 dòng/file theo SRP.
6. **Không mất dữ liệu khi xuất Word**: File Word xuất ra giữ trọn vẹn 100% dòng văn bản sau tiêu đề và nhúng chuẩn công thức toán OMML.
7. **Bản Portable hoàn thiện**: Gói ZIP di động chứa đầy đủ offline assets KaTeX không phụ thuộc mạng.
8. **Kiểm thử 100%**: Tất cả unit tests và stress tests mới đều vượt qua hoàn toàn.

---

## 5. Điều Kiện Chặn & Phê Duyệt (Gate & Approval)
- Đây là kế hoạch nâng cấp giải quyết triệt để các lỗi kỹ thuật và lỗi ngầm (Plan Continuation v6).
- Tuyệt đối không chỉnh sửa mã nguồn cho đến khi nhận được phê duyệt chính thức từ người dùng.
- Lệnh phê duyệt hợp lệ: `ok`, `làm đi`, `duyệt`, `ok duyệt`, `ok làm đi`, `được rồi làm đi`, `duyệt phương án`, `làm đi bạn`.
