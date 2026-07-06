---
task_name: "Di chuyển Tesseract-OCR vào src"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
---

# Kế hoạch di chuyển Tesseract-OCR vào src

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> - Gom thư mục `Tesseract-OCR` vào thư mục `src/`.
> - Cập nhật mã nguồn `app.py` để tìm đường dẫn Tesseract động (chế độ phát triển và chế độ build exe).
> - Giúp thư mục gốc `MDBANK` chỉ còn đúng 2 file chạy chính.

> [!NOTE]
> **[PHƯƠNG_PHÁP]**
> 1. Sửa `src/app.py`: check `sys.frozen` để thay đổi đường dẫn tìm `Tesseract-OCR/tesseract.exe` và `tessdata`.
> 2. Di chuyển thư mục `Tesseract-OCR/` -> `src/Tesseract-OCR/`.
> 3. Chạy build lại ứng dụng bằng `src/build.bat`.
> 4. Chạy thử phần mềm để kiểm chứng.

[ĐỀ_XUẤT_TỐI_ƯU]
Sử dụng phân nhánh logic trong Python dựa trên `sys.frozen` để giữ khả năng tương thích cao khi debug dev và phân phối exe.

> [!WARNING]
> **[CẢNH_BÁO]**
> Nếu đường dẫn tessdata (`TESSDATA_PREFIX`) trỏ sai, tính năng OCR hình ảnh/PDF sẽ lập tức bị lỗi khi chạy.

[NEO_HỒI_QUY]
Tất cả các cơ chế OCR và các thư viện hỗ trợ (pytesseract) không thay đổi.

---

## Chi tiết các tệp tin tác động (Impact Scope)

- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [NEW] `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/Tesseract-OCR` (Di chuyển từ gốc)
- [ ] [DELETE] `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/Tesseract-OCR`

---

## Kiến trúc Giải thuật & Mã giả (Pseudocode)

### Python (`src/app.py`):
```python
# Xác định đường dẫn Tesseract động trong LocalOcrImageConverter và LocalOcrPdfConverter:
if getattr(sys, 'frozen', False):
    # Khi chạy exe: tìm trong src/
    tesseract_local_meipass = os.path.join(self.base_dir_meipass, 'src', 'Tesseract-OCR', 'tesseract.exe')
    tesseract_local_exe = os.path.join(self.base_dir_exe, 'src', 'Tesseract-OCR', 'tesseract.exe')
    tessdata_local_meipass = os.path.join(self.base_dir_meipass, 'src', 'Tesseract-OCR', 'tessdata')
    tessdata_local_exe = os.path.join(self.base_dir_exe, 'src', 'Tesseract-OCR', 'tessdata')
else:
    # Khi dev: tìm cùng cấp với app.py
    tesseract_local_meipass = os.path.join(self.base_dir_meipass, 'Tesseract-OCR', 'tesseract.exe')
    tesseract_local_exe = os.path.join(self.base_dir_exe, 'Tesseract-OCR', 'tesseract.exe')
    tessdata_local_meipass = os.path.join(self.base_dir_meipass, 'Tesseract-OCR', 'tessdata')
    tessdata_local_exe = os.path.join(self.base_dir_exe, 'Tesseract-OCR', 'tessdata')
```
