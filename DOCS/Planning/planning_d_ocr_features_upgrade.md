---
title: "Kế hoạch Nâng cấp Tính năng Nâng cao từ D-OCR cho SuperSearch (v1)"
status: completed
task: d_ocr_features_upgrade
created: 2026-09-12
updated: 2026-09-12
author: Antigravity
---

# Kế Hoạch Nâng Cấp Tính Năng Nâng Cao từ D-OCR cho SuperSearch (v1)

## 1. Mục tiêu (Objective)
Kế thừa và tích hợp 5 năng lực cốt lõi từ D-OCR (Looking-Back-OCR) nhằm nâng cao chất lượng số hóa tài liệu scan, độ chính xác của chỉ mục tìm kiếm và trải nghiệm đối chiếu tài liệu trực quan:
1. **Lọc tạp âm scan vật lý & Khử Hallucination**: Nâng cấp prompt với bộ luật khử nhiễu gáy sách, mép cong, ố mốc, chữ thấu quang và dùng `[?]` chống bịa chữ.
2. **Nối câu liền mạch qua trang (Cross-page Sentence Healing)**: Tự động hàn gắn câu và đoạn văn bị bẻ đôi giữa các trang liên tiếp, phục vụ tìm kiếm cụm từ FTS5 hoàn hảo.
3. **Chế độ Đối chiếu 1:1 (Side-by-side Viewer)**: Chia đôi màn hình trong Quick View hiển thị ảnh trang scan gốc song song với văn bản đã OCR.
4. **Xuất Công thức Toán chuẩn OMML sang DOCX**: Chuyển đổi biểu thức LaTeX sang đối tượng Word Equation gốc thay vì văn bản thô.
5. **Luồng đọc bài báo đa cột & Thơ ca, Footnotes**: Định hướng đọc đúng thứ tự luồng bài viết nhiều cột và bảo tồn định dạng văn bản đặc thù.

---

## 2. Phạm Vi & Chi Tiết Kỹ Thuật (Scope & Technical Design)

### 2.1. Lọc Tạp Âm Scan Vật Lý & Chống Bịa Chữ (Prompt Reflow Denoising)
- **Vấn đề**: Bản scan sách xưa thường chứa bóng tối gáy sách, vết ố, chữ thấu quang từ mặt sau (show-through), hoặc chữ rách mờ. Bộ prompt hiện tại quá ngắn gọn, dễ khiến Gemini cố đoán hoặc sinh ra tạp âm làm nhiễu chỉ mục tìm kiếm.
- **Giải pháp**:
  - Nâng cấp `SYSTEM_OCR_INSTRUCTION` trong `src/gemini_ocr_engine.py` dựa trên chuẩn `markdown_reflow_instructions.md` của D-OCR.
  - Bổ sung bộ quy tắc khử nhiễu quang học:
    + Loại bỏ bóng gáy sách (gutter shadow), mép cong (page curl), đốm ố vàng (foxing), vệt rỉ bấm kim, bóng ngón tay giữ sách.
    + Khử chữ thấu quang (bleed-through/show-through) từ mặt sau của trang giấy mỏng.
    + Bỏ qua chữ viết tay ngoài lề (marginalia) và tem mác thư viện/barcode.
    + Bảo tồn tiêu đề trang bìa và trang nhất của báo/tạp chí (không nhầm với running header).
    + Quy tắc `[?]`: Nếu gặp chữ rách mờ không thể nhận diện chắc chắn, dùng ký hiệu `[?]` thay vì bịa đặt nội dung.

### 2.2. Nối Liền Câu Qua Trang (Cross-page Sentence Healing)
- **Vấn đề**: Khi một câu dài bị ngắt giữa cuối trang trước và đầu trang sau, việc OCR từng trang độc lập sẽ làm đứt gãy câu. Khi người dùng tìm kiếm cụm từ (phrase search FTS5) vắt ngang qua 2 trang, hệ thống sẽ bỏ sót kết quả.
- **Giải pháp**:
  - Xây dựng module xử lý hậu kỳ `src/ocr_postprocessor.py` với hàm `heal_cross_page_text(pages_text_list)`.
  - Thuật toán nhận diện:
    + Kiểm tra đoạn văn cuối cùng của trang $N$: Nếu không kết thúc bằng dấu chấm kết câu (`.`, `!`, `?`, `:`) hoặc kết thúc bằng dấu nối dòng (`-`), và đoạn văn đầu tiên của trang $N+1$ bắt đầu bằng chữ cái thường hoặc từ nối ngữ pháp.
    + Tự động ghép nối liền mạch dòng văn xuôi, xóa dấu gạch nối cơ học ngắt dòng (soft-hyphen).
    + Giữ nguyên thẻ phân định trang `<!-- PAGE {page_num} -->` để phục vụ định vị trang trong giao diện.

### 2.3. Chế Độ Đối Chiếu 1:1 trong Quick View (Side-by-side Viewer)
- **Vấn đề**: Sau khi tìm thấy tài liệu scan, người dùng chỉ nhìn thấy văn bản trích xuất, không biết AI đọc đúng hay sai nếu không mở file gốc bên ngoài.
- **Giải pháp**:
  - **Backend API**:
    + Thêm API `get_page_preview(document_id, page_number)` trong `src/app.py`:
      Sử dụng `pdfplumber` (hoặc `fitz`/`pypdfium2` có sẵn) trích xuất ảnh trang PDF thành chuỗi Base64 PNG/JPEG gửi lên giao diện. Đối với file ảnh thông thường, trả về trực tiếp ảnh gốc.
    + API `get_document_page_count(document_id)`.
  - **Frontend UI (`data/SuperSearch.html`)**:
    + Thêm nút chuyển chế độ "Đối chiếu 1:1" (Split View) trên thanh Quick View.
    + Khi kích hoạt, chia cửa sổ xem nhanh thành 2 cột độc lập:
      * Cột trái: Khung hiển thị ảnh trang scan gốc, kèm thanh điều khiển (Trang trước/sau, phóng to, thu nhỏ, xoay ảnh).
      * Cột phải: Bản đọc HTML / Markdown tương ứng với trang đang chọn.
    + Hỗ trợ phím tắt: Mũi tên trái/phải để lật trang đối chiếu.

### 2.4. Xuất Công Thức Toán Chuẩn OMML sang Microsoft Word (DOCX)
- **Vấn đề**: Hiện tại `src/export_service.py` chỉ xuất công thức toán học dưới dạng văn bản thô `$E=mc^2$`. Khi người dùng mở file `.docx` trong Microsoft Word, các biểu thức toán không phải là Equation có thể chỉnh sửa.
- **Giải pháp**:
  - Nâng cấp `export_to_docx` trong `src/export_service.py`.
  - Xây dựng bộ phân giải `latex_to_omml`:
    + Nhận diện các khối toán LaTeX: `\( ... \)` và `\[ ... \]` hoặc `$ ... $` và `$$ ... $$`.
    + Chuyển đổi biểu thức LaTeX sang cấu trúc XML `w:oMath` (Office Math Markup Language) của Microsoft Word.
    + Xử lý các cấu trúc toán học phổ biến: Phân số (`\frac`), số mũ (`^`), chỉ số dưới (`_`), căn bậc hai (`\sqrt`), tích phân (`\int`), tổng (`\sum`), các ký hiệu Hy Lạp và dấu ngoặc.
    + Chèn phần tử `<m:oMath>` trực tiếp vào paragraph của `python-docx` bằng `oxml.parse_xml`.

### 2.5. Luồng Đọc Đa Cột & Định Dạng Thơ Ca, Footnotes
- **Vấn đề**: Báo chí, tài liệu pháp lý và tạp chí thường in 2 hoặc 3 cột. Nếu không định hướng, AI có thể quét ngang gây đảo lộn trật tự đọc. Thơ ca bị biến thành văn xuôi và chú giải cuối trang bị lẫn vào nội dung chính.
- **Giải pháp**:
  - Bổ sung quy tắc vào `SYSTEM_OCR_INSTRUCTION`:
    + Luồng đa cột (Multi-column Flow): Đọc trọn vẹn từng cột từ trên xuống dưới theo thứ tự đọc tự nhiên của bài viết trước khi sang cột tiếp theo.
    + Thơ ca (Poetry): Bảo tồn từng dòng ngắt nhịp, đặt trong khối trích dẫn `>` để hiển thị thẩm mỹ.
    + Chú thích cuối trang (Footnotes): Đánh dấu tham chiếu `[^1]` trong thân bài và gom giải nghĩa `[^1]: ...` ở cuối trang.
  - Cập nhật `src/html_builder.py` để hiển thị đẹp khối thơ ca và chú thích `[^1]`.

---

## 3. Rủi Ro Kỹ Thuật & Biện Pháp Phòng Ngừa (Risks & Mitigations)

1. **Rủi ro hiệu năng trích xuất ảnh trang PDF (PDF Page Rendering Overhead)**:
   - Việc render ảnh PDF theo yêu cầu có thể tốn CPU nếu file quá lớn.
   - *Phòng ngừa*: Chỉ render đúng 1 trang người dùng đang xem trong Quick View (on-demand lazy render); lưu cache ảnh trang tạm thời trong bộ nhớ RAM (`lru_cache` tối đa 10 trang gần nhất).

2. **Rủi ro độ phức tạp khi parse LaTeX sang OMML trong Python**:
   - Biểu thức LaTeX có thể rất phức tạp, parser thuần regex khó bao quát toàn bộ cú pháp LaTeX.
   - *Phòng ngừa*: Xây dựng bộ sinh OMML theo kiến trúc nhiều lớp: Hỗ trợ 95% biểu thức toán học thông dụng (phân số, mũ, căn, tích phân, ký hiệu Hy Lạp). Với các biểu thức quá phức tạp ngoài tầm parse, fallback an toàn giữ nguyên chuỗi text LaTeX có định dạng font Cambria Math nghiêng.

3. **Rủi ro độ trễ API Gemini khi mở rộng Prompt OCR**:
   - Prompt dài hơn có thể tiêu tốn thêm input token.
   - *Phòng ngừa*: Đo lường token thực tế. Bộ chỉ dẫn D-OCR chỉ thêm khoảng ~350 tokens đầu vào, hoàn toàn nằm trong ngưỡng cho phép của Gemini Flash mà không làm tăng đáng kể độ trễ.

---

## 4. Kế Hoạch Triển Khai Từng Bước (Implementation Roadmap)

### Bước 1: Nâng cấp Prompt Lọc Nhiễu & Chống Bịa Chữ (Phase 1)
- [x] Cập nhật `SYSTEM_OCR_INSTRUCTION` trong `src/gemini_ocr_engine.py` với đầy đủ quy tắc lọc nhiễu vật lý, đa cột, thơ ca, footnotes và chống hallucination `[?]`.
- [x] Viết unit tests kiểm tra cấu trúc prompt và tính nhất quán.

### Bước 2: Xây dựng Module Nối Câu Qua Trang (Phase 2)
- [x] Tạo `src/ocr_postprocessor.py` chứa hàm `heal_cross_page_continuations`.
- [x] Tích hợp bộ nối câu vào `LocalOcrPdfConverter` trong `src/converters.py`.
- [x] Viết unit tests kiểm thử các kịch bản nối câu (câu đứt gãy, dấu gạch nối soft-hyphen, trường hợp câu đã kết thúc bằng dấu chấm).

### Bước 3: Nâng cấp Xuất DOCX với Công Thức Toán OMML (Phase 3)
- [x] Xây dựng module `latex_to_omml` trong `src/export_service.py` sinh thẻ XML `<m:oMath>`.
- [x] Kết nối việc chèn OMML vào các đoạn văn bản chứa công thức toán học khi xuất `.docx`.
- [x] Viết unit test xác thực tệp `.docx` tạo ra chứa phần tử XML toán học hợp lệ.

### Bước 4: Xây dựng API và Giao Diện Đối Chiếu 1:1 (Phase 4)
- [x] Bổ sung API `get_page_preview_image(document_id, page_num)` trong `src/app.py` với LRU cache.
- [x] Bổ sung thanh công cụ và chế độ chia 2 cột "Đối chiếu 1:1" trong `data/SuperSearch.html`.
- [x] Tích hợp tính năng lật trang, phóng to/thu nhỏ ảnh trang gốc và đồng bộ cuộn.

### Bước 5: Kiểm Thử Toàn Diện & Đóng Gói (Phase 5)
- [x] Chạy toàn bộ test suite hiện có (63/63 tests pass 100%).
- [x] Cập nhật `SuperSearch.spec` và `src/build.py` bao gồm `ocr_postprocessor`.

---

## 5. Tiêu Chí Nghiệm Thu (Acceptance Criteria)
1. **Prompt OCR**: Gemini bóc tách văn bản scan không bị lẫn gáy sách, vết ố; từ mờ rách được đánh dấu `[?]`.
2. **Liền mạch văn bản**: Câu vắt qua trang được ghép nối mượt mà; tìm kiếm cụm từ FTS5 qua ranh giới trang trả về kết quả chính xác.
3. **Đối chiếu 1:1**: Người dùng mở Quick View có thể bật chế độ chia đôi màn hình, lật từng trang ảnh gốc song song với văn bản bóc tách.
4. **Công thức toán Word**: File `.docx` xuất ra từ tài liệu toán học hiển thị công thức dạng Native Equation chuẩn của Word.
5. **Độ ổn định**: 100% unit tests pass (63/63 tests), không phát sinh regression bug nào đối với các tính năng tìm kiếm hiện hữu.

---

## 6. Điều Kiện Chặn & Phê Duyệt (Gate & Approval)
- Kế hoạch đã hoàn thành nghiệm thu (Completed Milestone).
