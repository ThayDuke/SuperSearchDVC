---
task_name: "Fix Document Indexing and Display Count"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "D:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
---

# Kế hoạch khắc phục lỗi hiển thị thiếu tài liệu

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Thư mục gốc `1CICTDATA` có 820 Files, 40 Folders.
> - Thư mục `MARKDOWN` tạo ra 610 Files (chính xác vì 132 file `.doc`/`.xls` nhị phân cũ không được hỗ trợ).
> - App SS chỉ hiển thị 264 tài liệu (bị loại bỏ 346 file do phân loại sai hoặc lỗi OCR).

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> 1. **Khắc phục lỗi race condition PDFium**:
>    - Thêm `self.ocr_lock = threading.Lock()` để đồng bộ hóa.
>    - Bọc `page.to_image()` và `pytesseract.image_to_string()` bằng `ocr_lock`.
> 2. **Sửa lỗi lọc trùng từ khóa**:
>    - Thay `"form" in rel_path_lower` bằng regex ranh giới từ `\b(form|forms|draft|drafts)\b`.
> 3. **Tối ưu bộ lọc biểu mẫu**:
>    - Không loại bỏ các biểu mẫu có lượng từ lớn (ví dụ `word_count >= 200` và mật độ placeholder thấp).

> [!WARNING]
> ### [CẢNH_BÁO]
> - Cần build lại file thực thi `SuperSearch.exe` sau khi sửa đổi mã nguồn `app.py`.
> - Các file `.doc` và `.xls` cũ cần được người dùng lưu thành `.docx` và `.xlsx` để được quét.

## Phạm vi Thay đổi

- [ ] [MODIFY] [app.py](file:///D:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

## Điểm neo Hành vi cốt lõi

- Giữ nguyên cấu trúc đầu ra `search_db.js`.
- Giữ nguyên logic phân loại tài liệu cơ bản.

## Kiến trúc Giải thuật & Mã giả

### 1. Đồng bộ hóa OCR trong `app.py`
```python
# Trong Api.__init__
self.ocr_lock = threading.Lock()

# Trong LocalOcrPdfConverter.convert
for page_num, page in enumerate(pdf.pages, 1):
    with self.api.ocr_lock:
        page_img = page.to_image(resolution=150)
        # ...
        text = pytesseract.image_to_string(img, lang='vie+eng')

# Trong LocalOcrImageConverter.convert
with self.api.ocr_lock:
    img = Image.open(file_stream)
    text = pytesseract.image_to_string(img, lang='vie+eng')
```

### 2. Sửa lỗi `in_biem_mau` và logic phân loại template
```python
# Khớp từ độc lập để tránh khớp nhầm "information"
in_biem_mau = bool(re.search(r'\b(form|forms|draft|drafts)\b', rel_path_lower)) or "biểu mẫu" in rel_path_lower

# Cải tiến phân loại biểu mẫu
if in_biem_mau:
    if word_count < 200:
        if total_placeholders > 1 or density > 0.02:
            is_template = True
    else:
        if density > 0.15:
            is_template = True
```

## Quy trình Xác minh

### Kiểm thử Thủ công
1. Chạy quét thư mục `1CICTDATA`.
2. Kiểm tra log và số lượng tài liệu hiển thị trong App SS (kỳ vọng hiển thị nhiều hơn 264 tài liệu).
3. Đảm bảo các file PDF không còn chứa nội dung lỗi `Error during local OCR: Failed to load page.`.
