---
task_name: "Tích hợp OCR local Tesseract"
date: "2026-07-01"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.spec"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/build.bat"
---

# Kế hoạch Tích hợp Tesseract OCR cục bộ cho SuperSearch (SS)

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> - Thay thế tính năng OCR dùng Gemini API trực tuyến bằng OCR offline sử dụng Tesseract cục bộ.
> - Sao chép thư mục Tesseract làm tài nguyên độc lập để ứng dụng (SS) chạy trực tiếp không phụ thuộc cài đặt.
> - Giữ nguyên dung lượng tối ưu và các logic tìm kiếm sẵn có.

## Phạm vi thay đổi
- [ ] [NEW] Sao chép `C:\Program Files\Tesseract-OCR` -> `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/Tesseract-OCR`
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/app.py)
- [ ] [MODIFY] [SuperSearch.spec](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.spec)
- [ ] [MODIFY] [build.bat](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/build.bat)

## Điểm neo hành vi cốt lõi
- Logic của hàm `Api.scan_and_index` trong việc phân loại tài liệu, tạo thư mục `ORIGINAL` / `MARKDOWN` và ghi cơ sở dữ liệu `search_db.js`.
- Logic nhận diện ngôn ngữ tiếng Anh/tiếng Việt và phân loại tên loại văn bản.

## Kiến trúc giải thuật & Mã giả (Pseudocode)

### 1. Khai báo Class Converter OCR Offline cho PDF và Ảnh
```python
# Cấu hình đường dẫn Tesseract
pytesseract.pytesseract.tesseract_cmd = path_to_tesseract

class LocalOcrPdfConverter(DocumentConverter):
    def accepts(self, stream, stream_info):
        # Trả về True nếu là file .pdf
        pass
        
    def convert(self, stream, stream_info):
        # 1. Trích xuất text thường bằng pdfplumber
        # 2. Nếu trống/ít chữ, duyệt từng trang PDF render thành ảnh PNG
        # 3. Chạy OCR cục bộ (pytesseract) với config vie+eng và thư mục tessdata ngoài
        # 4. Trả về kết quả văn bản dạng markdown
        pass

class LocalOcrImageConverter(DocumentConverter):
    def accepts(self, stream, stream_info):
        # Trả về True nếu là .png, .jpg, .jpeg
        pass
        
    def convert(self, stream, stream_info):
        # OCR ảnh trực tiếp qua pytesseract
        pass
```

### 2. Đăng ký trong Api.scan_and_index
```python
# Khởi tạo MarkItDown
md_converter = MarkItDown()
# Đăng ký 2 bộ OCR cục bộ mới với priority = -1.0 để chạy trước bộ chuyển đổi mặc định
md_converter.register_converter(LocalOcrPdfConverter(base_dir), priority=-1.0)
md_converter.register_converter(LocalOcrImageConverter(base_dir), priority=-1.0)
```

[ĐỀ_XUẤT_TỐI_ƯU]
- Nạp động đường dẫn Tesseract-OCR tùy theo môi trường chạy (sử dụng sys._MEIPASS khi đóng gói exe hoặc thư mục MDBANK/Tesseract-OCR khi chạy code python).
- Trỏ thư mục tessdata tới `CONVERSION_LOGS/tessdata` trong dự án để tận dụng file dữ liệu ngôn ngữ có sẵn.

> [!WARNING]
> **[CẢNH_BÁO]**
> - Thư mục Tesseract-OCR rất nhiều file con, việc đóng gói trực tiếp vào exe thông qua spec file sẽ làm dung lượng exe tăng mạnh (~150MB) và tốc độ giải nén khi khởi chạy SS chậm hơn.
> - Giải pháp thay thế là đặt thư mục Tesseract-OCR nằm cạnh exe (không nén vào trong exe) để khởi động nhanh hơn. Ở đây chúng tôi đề xuất đưa cấu hình Tesseract-OCR vào spec để đóng gói một file duy nhất cho tiện phân phối theo yêu cầu người dùng.

[NEO_HỒI_QUY]
- Cơ chế bỏ qua file đã chuyển đổi thành công trong `MARKDOWN`.
- Giao diện người dùng HTML/CSS/JS.

## Kế hoạch kiểm thử thủ công
1. Chạy quét một file PDF scan mới hoặc file ảnh PNG/JPG mới.
2. Kiểm tra xem file `.md` mới sinh ra trong thư mục `MARKDOWN` có chứa nội dung văn bản tiếng Việt/tiếng Anh được OCR offline bởi Tesseract hay không.
3. Kiểm tra xem file `search_db.js` có được cập nhật dữ liệu mới chính xác hay không.
