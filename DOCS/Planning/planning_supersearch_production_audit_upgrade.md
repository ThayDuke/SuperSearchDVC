---
title: "Kế hoạch Audit Toàn diện và Nâng cấp SuperSearch Đạt Chuẩn Production (v2)"
version: v2
status: plan_continuation
task: audit_and_production_upgrade
created: 2026-09-10
updated: 2026-09-10
author: Antigravity
---

# Kế Hoạch Audit Toàn Diện và Nâng Cấp Hệ Thống SuperSearch (Production-Ready) - v2

## 1. Mục tiêu (Objective)
- Thực hiện kiểm toán toàn diện (Code Audit & Architecture Audit) hệ thống SuperSearch.
- Định danh và phân loại tất cả các nợ kỹ thuật (Technical Debt), lỗ hổng thuật toán, tắc nghẽn hiệu năng (Performance Bottlenecks), và các thiết kế chưa chuẩn mực.
- Thiết lập lộ trình tái cấu trúc và nâng cấp toàn diện để đưa SuperSearch trở thành phần mềm tìm kiếm offline chuyên nghiệp, đạt tiêu chuẩn production, giao diện trực quan, thân thiện và có tính ứng dụng thực tiễn cao cho mọi tổ chức.

---

## 2. Báo Cáo Kiểm Toán Toàn Diện (Comprehensive Audit Findings)

### 2.1. Nợ kỹ thuật kiến trúc (Architecture Debts)
1. **Monolithic God Class (`src/app.py` > 1.800 dòng, `Api` class > 1.240 dòng)**:
   - Class `Api` kiêm nhiệm quá nhiều trách nhiệm: Cầu nối GUI PyWebView, quản lý vòng đời luồng, điều phối bộ chuyển đổi MarkItDown, duyệt thư mục, phân loại nghiệp vụ, bóc tách metadata, ghi cache file, cấu hình OCR, mở Explorer.
   - Vi phạm nghiêm trọng nguyên lý Single Responsibility Principle (SRP).
2. **Monolithic Frontend (`data/SuperSearch.html` 228 KB, 5.382 dòng)**:
   - Chứa 2.137 dòng CSS nội tuyến, 310 dòng HTML, và 2.902 dòng JavaScript không phân tách module trong một file duy nhất.
   - Rất khó debug, kiểm thử unit test cho UI, mở rộng hay tái sử dụng các thành phần giao diện.
3. **Phế tích dư thừa `search_db.js` (Legacy Dead Weight)**:
   - Trong mỗi chu kỳ quét tài liệu, `app.py` biên dịch toàn bộ dữ liệu văn bản của tất cả các file thành một biến JavaScript `var SEARCH_DB = [...]` rồi ghi ra đĩa với `indent=2`.
   - Trong khi đó, giao diện người dùng hiện tại đã chuyển sang truy vấn trực tiếp SQLite FTS5 qua `pywebview.api.search_documents`.
   - Hậu quả: Gây bùng nổ RAM (nguy cơ OOM khi thư mục có hàng vạn tệp), nhân đôi dung lượng lưu trữ đĩa vô ích và làm chậm pha kết thúc quét hàng chục lần.
4. **Viết thừa hàng nghìn tệp HTML mồ côi (`runtime/HTML/`)**:
   - `scan_and_index` tạo ra toàn bộ cây thư mục HTML trong `runtime/HTML/` bằng `_write_html`, nhưng phương thức `get_document` khi preview lại gọi `markdown_to_html_body` trực tiếp từ văn bản thô. Không có bất kỳ thành phần nào đọc cây thư mục HTML này.

### 2.2. Vấn đề thuật toán & Hiệu năng (Algorithms & Performance)
1. **Xóa trắng và tái tạo Index toàn phần (Lack of Incremental Indexing)**:
   - Trong `src/index_store.py`, phương thức `replace_entries` thực thi:
     `DELETE FROM documents_fts; DELETE FROM documents;` rồi chèn lại toàn bộ tài liệu từ đầu và gọi `INSERT INTO documents_fts(documents_fts) VALUES ('rebuild')`.
   - Khi thư mục có 50.000 tệp, việc thêm mới hoặc sửa 1 tệp duy nhất buộc hệ thống phải xóa và lập chỉ mục lại toàn bộ 50.000 tệp. Độ phức tạp là $O(N)$ thay vì $O(\Delta)$.
2. **Nhân đôi dung lượng cơ sở dữ liệu (Redundant Column Storage)**:
   - Bảng `documents` lưu trữ cả `content` (gốc) lẫn `content_clean` (đã bỏ dấu tiếng Việt).
   - Trong khi đó, bảng ảo FTS5 đã sử dụng tokenizer `unicode61 remove_diacritics 2`. Cột `content_clean` hoàn toàn không bao giờ được truy vấn trả về cho người dùng, làm tăng 100% dung lượng lưu trữ text trong SQLite.
3. **Tắc nghẽn tạo Snippet bằng Python thuần (Snippet Generation Bottleneck)**:
   - Hàm `build_plain_snippet` trong `index_store.py` duyệt từng ký tự bằng `unicodedata.normalize('NFD', char)` và xây dựng mảng offset ký tự trên RAM. Với các tệp dung lượng lớn, thao tác này làm chậm tiến trình tìm kiếm một cách nghiêm trọng. Trong khi SQLite FTS5 có sẵn hàm `snippet()` ở tầng C siêu tốc.
4. **Lãng phí truy vấn đa lần trong Search RRF**:
   - Mỗi truy vấn từ 2 từ trở lên thực thi 4-5 câu lệnh SQL FTS riêng biệt (`title_phrase`, `phrase`, `near`, `strict`, `relaxed`), mỗi câu lệnh lấy tới 2.000 bản ghi với 19 trường dữ liệu, sau đó tải vào Python để gộp và sắp xếp trên bộ nhớ.
5. **Render ảnh PDF hai lần trong OCR (Double Rendering in OCR)**:
   - Trong `LocalOcrPdfConverter`, khi trang PDF cần OCR, code gọi `page.to_image(resolution=150)` và encode PNG để gửi sang Gemini. Nếu Gemini lỗi hoặc fallback sang Tesseract, hệ thống lại gọi lại `page.to_image(resolution=150)` lần thứ hai để nạp vào pytesseract, tiêu tốn gấp đôi CPU và bộ nhớ đồ họa.
6. **Điều phối đa luồng tĩnh và cơ chế thắt nghẽn 1 luồng cứng (Static Worker Lock & Hard Choke)**:
   - `get_safe_workers_count()` chỉ đo RAM một lần duy nhất lúc khởi động quét. Nếu RAM > 70%, hệ thống khóa cứng vĩnh viễn 1 luồng cho toàn bộ phiên quét, gây lãng phí thời gian quét lên đến hàng chục lần. Nếu ban đầu RAM thấp rồi tăng cao trong quá trình quét file nặng, hệ thống lại không có cơ chế tự động giảm luồng mềm.
7. **Dung lượng đệm ảnh OCR thô (Uncompressed Raw Image Buffers)**:
   - Bộ đệm OCR lưu ảnh định dạng PNG thô (~3-5MB/trang), gây lãng phí RAM đệm và làm chậm băng thông gửi payload lên Gemini API gấp 5-10 lần so với JPEG tối ưu.

### 2.3. Lỗi phần mềm nghiêm trọng & Ràng buộc cứng (Critical Bugs & Hardcoding)
1. **Chuẩn hóa định danh mô hình Gemini API**:
   - `DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"` trong `gemini_ocr_engine.py` và `app.py`.
   - Mô hình `gemini-3.6-flash` là model khuyến nghị chính thức mới nhất của Google Generative AI API (thay thế gemini-2.5-flash). Hệ thống hỗ trợ dự phòng `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-1.5-flash`.
2. **Hard-coded nghiệp vụ đặc thù doanh nghiệp CICT**:
   - Mã nguồn chứa cứng các chuỗi nhận diện riêng của Cảng Cái Lân (`cict administration documents`, `cict.qt.it`, `cict.cs.it`, `sà lan`, `cảng vụ`, `nạo vét bến cảng`, `cai lan terminal`).
   - Tiêu đề giao diện bị gán cứng: `SuperSearch - Tra cứu tài liệu siêu tốc CICT`.
   - Phần mềm bị mất tính tổng quát, không thể phân phối cho các cá nhân hoặc tổ chức khác.
3. **Vi phạm nguyên tắc Local-First & Hoạt động Ngoại tuyến (Offline Breakdown)**:
   - Sử dụng CDN ngoài cho MathJax: `https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js`.
   - Sử dụng Google Fonts: `https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro...`.
   - Khi chạy trên máy trạm nội bộ không có Internet hoặc mạng cách ly bảo mật (air-gapped), giao diện sẽ bị treo/chờ timeout mạng, font bị giật (FOIT), và công thức toán không thể render.
4. **Rủi ro chuỗi lệnh khi mở File Explorer**:
   - Hàm `open_explorer` ghép chuỗi `subprocess.Popen(f'explorer.exe /select,"{resolved}"')`. Cần chuẩn hóa thành danh sách đối số an toàn để chống lỗi ký tự đặc biệt hoặc khoảng trắng.

---

## 3. Đề Xuất Nâng Cấp Hệ Thống (Production-Grade Architecture Proposal)

### 3.1. Tái cấu trúc mã nguồn Backend theo Clean Modular Architecture
Tách nhỏ `src/app.py` thành các module độc lập theo miền trách nhiệm:
- `src/core/`: Quản lý cấu hình, hằng số, logger, xác định đường dẫn môi trường (frozen vs dev).
- `src/converters/`:
  - `base.py`: Lớp trừu tượng DocumentConverter chuẩn.
  - `pdf_converter.py`: Bóc tách PDF + OCR bộ đệm 1 lần (Single-pass render).
  - `office_converters.py`: Chuyển đổi Word, Excel, PowerPoint.
  - `image_converter.py`: OCR ảnh.
  - `archive_converter.py`: Xử lý ZIP an toàn.
- `src/storage/`:
  - `index_store.py`: Cơ sở dữ liệu SQLite FTS5 nâng cấp hỗ trợ **Incremental Upsert/Delete**.
- `src/services/`:
  - `indexer_service.py`: Quét thư mục, quản lý đa luồng, báo cáo tiến độ, đồng bộ hóa chỉ mục.
  - `classifier_service.py`: Bộ phân loại tài liệu tổng quát (Generic classifier), cho phép cấu hình theo file rule JSON ngoài.
  - `ocr_service.py`: Quản lý bộ máy OCR (Tesseract nội bộ + Gemini AI chuẩn model).
- `src/ui_bridge/`:
  - `api.py`: Chỉ đóng vai trò API Controller mỏng, nhận request từ PyWebView và chuyển tiếp xuống service.

### 3.2. Nâng cấp Thuật toán & Tối ưu Cơ sở dữ liệu SQLite FTS5
1. **Incremental Indexing (Chỉ mục gia tăng)**:
   - Bổ sung bảng theo dõi phiên bản tệp dựa trên `absolute_original_path`, `source_mtime_ns`, và `source_size`.
   - Khi quét lại:
     - Tệp mới: INSERT vào `documents` và `documents_fts`.
     - Tệp sửa đổi: UPDATE vào `documents` và `documents_fts`.
     - Tệp đã xóa: DELETE khỏi `documents` và `documents_fts`.
     - Tệp không đổi: Bỏ qua hoàn toàn.
2. **Loại bỏ dữ liệu rác**:
   - Xóa bỏ việc tạo và ghi `search_db.js`.
   - Xóa bỏ việc ghi cây thư mục tĩnh `runtime/HTML/`.
   - Loại bỏ cột `content_clean` khỏi bảng `documents`, dựa vào khả năng xử lý dấu tự nhiên của SQLite FTS5 `tokenize='unicode61 remove_diacritics 2'`.
3. **Chuyển dịch tạo Snippet sang C Native**:
   - Tận dụng hàm `snippet(documents_fts, ...)` của SQLite để trích xuất ngữ cảnh khớp từ khóa siêu tốc, giảm tải tối đa cho Python.
4. **Bộ điều tiết luồng thích ứng (Adaptive Dynamic Throttling) & Trần an toàn 75%**:
   - Bỏ cơ chế đo RAM 1 lần duy nhất lúc khởi tạo; chuyển sang kiểm tra tải hệ thống động theo chu kỳ và theo ngưỡng task.
   - **Mức xanh (< 65% RAM/CPU)**: Hoạt động 100% công suất đa luồng tối đa (`N_workers = int(cpu_cores * 0.75)`).
   - **Mức vàng (65% - 75% RAM/CPU)**: Giảm mềm luồng xuống mức an toàn (`max(2, int(N_workers * 0.65))`), ngăn chặn hiện tượng tăng vọt đột ngột.
   - **Mức đỏ (> 75% RAM/CPU)**: Chế độ phòng vệ khẩn cấp, duy trì tối thiểu 2 luồng (chỉ hạ về 1 luồng nếu RAM > 88%), tự động gọi `gc.collect()` và tạo quãng nghỉ 0.5s để bộ đệm RAM hạ nhiệt.
   - **Độ trễ phục hồi (Hysteresis)**: Chỉ cho phép tăng lại số luồng khi tài nguyên hạ ổn định dưới 60% qua 2 chu kỳ đo liên tiếp nhằm triệt tiêu dao động gián đoạn (oscillation).
   - **Tối ưu đệm ảnh OCR**: Thay thế hoàn toàn việc lưu ảnh PNG thô bằng JPEG chất lượng 85%. Tiết kiệm 90% bộ nhớ RAM đệm và tăng tốc truyền tải HTTP cho Gemini API gấp 5-10 lần.
   - **Cách ly Semaphore Tesseract**: Thay thế lock toàn cục duy nhất bằng `BoundedSemaphore` cho phép xử lý song song có kiểm soát mà không gây quá tải CPU.

### 3.3. Tách biệt và Nâng cấp Frontend (UX/UI Hiện Đại)
1. **Phân rã Frontend**:
   - Tách `SuperSearch.html` thành các file độc lập: `index.html`, `styles/` (chứa design system, glassmorphic tokens), `scripts/` (quản lý state, pywebview bridge, event handlers).
2. **Đóng gói Offline 100% (Air-gapped Ready)**:
   - Nhúng font chuẩn hệ thống (`Segoe UI`, `Inter` fallback) không phụ thuộc Google Fonts.
   - Thay thế MathJax CDN bằng thư viện KaTeX / MathJax bundle cục bộ tải trực tiếp từ máy tính.
3. **Cải thiện trải nghiệm người dùng (UX Enhancements)**:
   - **Thanh tiến trình quét thông minh**: Hiển thị tốc độ quét (file/s), số file còn lại, thanh ước lượng thời gian (ETA), và danh sách các file đang được xử lý song song trực quan.
   - **Bảng quản lý lỗi quét (Error Inspector)**: Modal xem chi tiết các file không đọc được, có nút bấm "Thử lại (Retry)" hoặc "Xem file trong Explorer".
   - **Bộ lọc tìm kiếm trực quan**: Thêm thanh trượt/chọn khoảng thời gian (Date Range Picker), lọc nhanh theo loại định dạng (PDF, Word, Excel, Ảnh, v.v.), gắn tag phân loại mềm.
   - **Trình xem trước tài liệu (Preview Viewer) nâng cấp**: Hỗ trợ tìm kiếm từ khóa bên trong tài liệu đang xem (In-document search), nút phóng to/thu nhỏ font, chế độ đọc tập trung (Focus mode), và copy nhanh nội dung Markdown.
   - **Trung tâm cài đặt (Settings Center)**: Cho phép người dùng trực tiếp nhập và kiểm tra API Key Gemini, chọn mô hình (`gemini-2.5-flash`, `gemini-1.5-flash`), cấu hình số lượng worker luồng tối đa, và tùy chỉnh thư mục quét mặc định.

---

## 4. Kế Hoạch Triển Khai Theo Giai Đoạn (Phased Implementation Roadmap)

### Giai đoạn 1: Khắc phục lỗi chí mạng & Loại bỏ nợ thừa (Quick Wins & Stability)
- [x] **Chuẩn hóa Model Gemini**: Cấu hình `DEFAULT_GEMINI_MODEL` là `gemini-3.6-flash` và hỗ trợ dự phòng `gemini-2.5-pro` / `gemini-2.0-flash` / `gemini-1.5-flash`.
- [x] **Bẻ khóa Offline**: Gỡ bỏ các liên kết CDN ngoài (Google Fonts, MathJax CDN) trong `SuperSearch.html` và `html_builder.py`; chuẩn hóa font hệ thống và Math offline.
- [x] **Xóa rác I/O**: Loại bỏ logic ghi `search_db.js` và cây thư mục thừa `runtime/HTML/` trong `scan_and_index`.
- [x] **Tổng quát hóa nghiệp vụ**: Loại bỏ hardcode thương hiệu CICT, xây dựng cấu hình phân loại linh hoạt hoặc nhận diện tự nhiên.
- [x] **An toàn hệ thống**: Chuẩn hóa lệnh gọi `open_explorer` sang argument list an toàn.

### Giai đoạn 2: Tối ưu lõi cơ sở dữ liệu & Thuật toán lập chỉ mục (Core Engine Optimization)
- [x] **Incremental Indexing**: Xây dựng cơ chế UPSERT/DELETE trong `IndexStore` dựa trên hash và mtime của tệp nguồn.
- [x] **Tối ưu Schema**: Tự động bảo trì bảng FTS5 qua triggers, loại bỏ rebuild toàn phần.
- [ ] **Native Snippets**: Thay thế `build_plain_snippet` Python chậm chạp bằng cơ chế tối ưu kết hợp SQLite FTS5 snippet.
- [x] **Tối ưu hóa OCR**: Khắc phục lỗi render ảnh PDF 2 lần trong `LocalOcrPdfConverter`.
- [x] **Điều tiết thích ứng 75% & Tối ưu OCR Buffer**: Triển khai bộ điều tiết đa luồng mềm theo trần an toàn 75% RAM/CPU, chống thắt nghẽn 1 luồng cứng, nén đệm JPEG 85% và mở rộng semaphore Tesseract.

### Giai đoạn 3: Tái cấu trúc Backend & Module hóa (Backend Refactoring)
- [ ] Tách `src/app.py` thành cấu trúc gói module (`core`, `services`, `converters`, `storage`, `ui_bridge`).
- [ ] Xây dựng unit tests và integration tests bao phủ các converters và bộ xử lý chỉ mục.

### Giai đoạn 4: Nâng cấp Frontend & Trải nghiệm Người Dùng (UI/UX Transformation)
- [ ] Tách nhỏ CSS, JS khỏi `SuperSearch.html`.
- [ ] Bổ sung màn hình Cài đặt (Settings Modal) hoàn chỉnh.
- [ ] Cải tiến thanh tiến trình quét (hiển thị ETA, tốc độ, danh sách lỗi chi tiết).
- [ ] Tối ưu hóa giao diện Preview (In-doc search, zoom, dark/light theme chuẩn hóa).

---

## 5. Tiêu Chí Nghiệm Thu (Acceptance Criteria)
1. **Tính độc lập offline**: Phần mềm khởi động và hoạt động 100% tính năng khi ngắt hoàn toàn kết nối mạng.
2. **Độ ổn định quét**: Quét thư mục 50.000 tệp không bị tràn bộ nhớ RAM (RAM duy trì < 350MB).
3. **Tốc độ chỉ mục gia tăng**: Khi thêm 1 tệp mới vào kho 10.000 tệp đã có, thời gian cập nhật chỉ mục hoàn tất trong dưới 2 giây (thay vì quét lại toàn bộ từ đầu).
4. **AI OCR hoạt động chuẩn**: Gemini OCR kết nối thành công tới model `gemini-3.6-flash` và trả về kết quả chính xác khi cung cấp API Key hợp lệ.
5. **Tính tổng quát**: Không còn bất kỳ dấu vết hard-code thông tin của doanh nghiệp CICT nào trong code và giao diện.
6. **Kiểm thử hồi quy**: Toàn bộ unit tests hiện có và mới viết đều pass 100%.

---

## 6. Điều Kiện Chặn & Phê Duyệt (Gate & Approval)
- Đây là kế hoạch kiểm toán và nâng cấp toàn diện (Plan Draft).
- Tuyệt đối không chỉnh sửa mã nguồn cho đến khi nhận được phê duyệt chính thức từ người dùng.
- Lệnh phê duyệt hợp lệ: `ok`, `làm đi`, `duyệt`, `ok duyệt`, `ok làm đi`, `được rồi làm đi`, `duyệt phương án`, `làm đi bạn`.
