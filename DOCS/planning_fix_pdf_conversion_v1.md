---
task_name: "Fix lỗi PDF convert thất bại (PDFium Data format error) trong môi trường đóng gói"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
---

# Lập kế hoạch fix lỗi PDF convert thất bại (OCR Error)

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> 1. **Hiện tượng lỗi:** Có 201 file PDF bị lỗi convert trong thư mục `MARKDOWN`. File `.md` tương ứng chứa nội dung lỗi: `Error during local OCR: Failed to load document (PDFium: Data format error)`.
> 2. **Nguyên nhân:** Khi chạy file đóng gói `SuperSearch.exe`, việc truyền stream `io.BytesIO` cho `pdfplumber` (và `pypdfium2` bên dưới) trong môi trường đa luồng qua ctypes callback bị xung đột hoặc lỗi định dạng dữ liệu, dẫn đến PDFium không load được document từ stream.
> 3. **Mục tiêu:**
>    - Khắc phục triệt để lỗi load document bằng cách mở trực tiếp từ file path thay vì stream khi có thể.
>    - Tự động phát hiện và convert lại các file `.md` đã bị lỗi từ trước mà không cần người dùng thao tác thủ công.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Giữ nguyên logic trích xuất text qua `pdfplumber` trước khi OCR.
- Giữ nguyên logic chạy OCR qua `pytesseract` và cấu hình thư mục Tesseract cục bộ/toàn cục.

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> 1. **Ưu tiên mở file trực tiếp từ đĩa:**
>    - Trong class `LocalOcrPdfConverter.convert`, kiểm tra xem `stream_info.local_path` có tồn tại và hợp lệ không.
>    - Nếu có, gọi `pdfplumber.open(stream_info.local_path)` trực tiếp.
>    - Nếu không (ví dụ file từ nguồn stream thuần), fallback về dùng `pdf_bytes` (`io.BytesIO`).
>    - Việc nạp trực tiếp file path giúp PDFium C++ đọc trực tiếp từ OS, tránh qua callback của Python ctypes, giải quyết triệt để lỗi format error trong môi trường frozen.
> 2. **Tự động quét và ghi đè các file lỗi cũ:**
>    - Trong hàm `scan_and_index` (vòng lặp duyệt file nguồn), kiểm tra nếu file `.md` tương ứng đã tồn tại:
>      - Đọc thử 200 ký tự đầu của file `.md`.
>      - Nếu chứa chuỗi `"Error during local OCR:"`, đánh dấu file này đã bị lỗi (corrupted).
>      - Xóa file `.md` lỗi đó và thêm file gốc tương ứng vào danh sách tác vụ convert (`tasks`).

[ĐỀ_XUẤT_TỐI_ƯU]
- Việc tự động phát hiện file lỗi giúp khôi phục toàn bộ 201 file bị hỏng một cách tự động trong lượt quét tiếp theo mà không yêu cầu người dùng phải dọn dẹp thư mục trước.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Do 201 file `.md` bị lỗi sẽ được xóa và convert lại, lượt quét đầu tiên sau khi cập nhật code có thể mất nhiều thời gian hơn (do chạy OCR Tesseract cho cả 201 file này). Người dùng cần kiên nhẫn chờ thanh tiến trình chạy xong.

[NEO_HỒI_QUY]
- Đảm bảo logic fallback `pdf_bytes` vẫn hoạt động bình thường trong trường hợp không có `local_path`.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Cải tiến `LocalOcrPdfConverter.convert` trong [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

```python
# Lớp LocalOcrPdfConverter
class LocalOcrPdfConverter(DocumentConverter):
    # ... init ...

    def convert(self, file_stream, stream_info, **kwargs):
        # ... setup tesseract path ...

        # Lấy file path trực tiếp nếu có
        pdf_target = None
        if stream_info and stream_info.local_path and os.path.exists(stream_info.local_path):
            pdf_target = stream_info.local_path

        text_content = []
        try:
            # Mở tài liệu trực tiếp bằng path hoặc fallback stream
            if pdf_target:
                with pdfplumber.open(pdf_target) as pdf:
                    # Trích xuất text như cũ
            else:
                file_stream.seek(0)
                pdf_bytes = io.BytesIO(file_stream.read())
                with pdfplumber.open(pdf_bytes) as pdf:
                    # Trích xuất text như cũ
        except Exception:
            pass

        full_text = "\n\n".join(text_content).strip()

        # Nếu cần chạy OCR
        if not full_text or len(full_text) < 100:
            ocr_pages = []
            try:
                if pdf_target:
                    with pdfplumber.open(pdf_target) as pdf:
                        # Vòng lặp các trang và page.to_image() -> pytesseract
                else:
                    file_stream.seek(0)
                    pdf_bytes = io.BytesIO(file_stream.read())
                    with pdfplumber.open(pdf_bytes) as pdf:
                        # Vòng lặp các trang và page.to_image() -> pytesseract
                full_text = "\n\n".join(ocr_pages).strip()
            except Exception as e:
                full_text = f"Error during local OCR: {str(e)}"

        return DocumentConverterResult(markdown=full_text)
```

### 2. Tự động phát hiện và ghi đè file lỗi trong `scan_and_index`

```python
# Trong scan_and_index:
for file in files:
    # ... kiểm tra extension ...
    if ext in supported_extensions:
        # ... xác định new_markdown_path ...
        
        is_corrupted = False
        if os.path.exists(new_markdown_path):
            try:
                # Đọc kiểm tra xem file md có chứa thông báo lỗi OCR không
                with open(new_markdown_path, 'r', encoding='utf-8', errors='ignore') as f_check:
                    head = f_check.read(200)
                    if "Error during local OCR:" in head:
                        is_corrupted = True
            except Exception:
                pass

        if not os.path.exists(new_markdown_path) or is_corrupted:
            if is_corrupted:
                try:
                    os.remove(new_markdown_path)
                except Exception:
                    pass
            tasks.append({
                'src_path': file_path,
                'dest_md_path': new_markdown_path,
                'dest_orig_path': None,
                'clean_src_after': False
            })
```

## Kế hoạch kiểm thử thủ công (Verification Plan)
1. Chạy app `SuperSearch` từ môi trường dev hoặc build exe mới.
2. Thực hiện quét (Scan) thư mục chứa các file PDF bị lỗi trước đó.
3. Xác nhận rằng thanh tiến trình chạy bình thường, và các file bị lỗi cũ đã được convert lại thành công (nội dung hiển thị text trích xuất hoặc OCR chính xác thay vì dòng chữ báo lỗi).
