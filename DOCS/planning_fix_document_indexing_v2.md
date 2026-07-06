---
task_name: "Fix Document Indexing and Support Old Formats"
date: "2026-07-03"
version: "v2"
status: "Draft"
target_files:
  - "D:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
---

# Kế hoạch khắc phục lỗi hiển thị thiếu tài liệu & Hỗ trợ định dạng Office cũ

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Cần quét và hiển thị đầy đủ tài liệu bao gồm cả định dạng mới và cũ của hệ sinh thái Microsoft Office.
> - Hỗ trợ các file nhị phân cũ `.doc` (122 file) và `.xls` (10 file) mà không cần máy người dùng cài Office.
> - Sửa triệt để các lỗi lọc template sai và race condition gây lỗi OCR trong `app.py`.

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> 1. **Cài đặt thư viện bổ sung**: Cài đặt `xlrd` vào thư mục `src/Lib` để đọc tệp `.xls`.
> 2. **Xây dựng bộ chuyển đổi tùy chỉnh**:
>    - Định nghĩa `LocalDocConverter` đọc stream `WordDocument` của file `.doc` thông qua thư viện `olefile` (đã có sẵn) và giải mã văn bản UTF-16LE/ASCII sạch.
>    - Định nghĩa `LocalXlsConverter` đọc và phân tích cấu trúc bảng tính `.xls` thông qua thư viện `xlrd`, định dạng lại thành bảng Markdown.
>    - Đăng ký cả hai bộ chuyển đổi này vào `MarkItDown`.
> 3. **Đồng bộ hóa tránh lỗi OCR**: Dùng `threading.Lock()` đồng bộ hóa OCR và render.
> 4. **Khắc phục lỗi nhận diện biểu mẫu**: Sửa điều kiện nhận diện `in_biem_mau` dùng regex độc lập từ.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Việc giải mã trực tiếp tệp nhị phân `.doc` thô qua stream `WordDocument` sẽ bỏ qua các định dạng trang trí phức tạp (font chữ, màu sắc), nhưng giữ lại 100% nội dung chữ có nghĩa để đảm bảo khả năng tìm kiếm (SuperSearch).

## Phạm vi Thay đổi

- [ ] [MODIFY] [app.py](file:///D:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

## Điểm neo Hành vi cốt lõi

- Giữ nguyên cấu trúc JSON của cơ sở dữ liệu `search_db.js`.

## Kiến trúc Giải thuật & Mã giả

### 1. Khai báo mở rộng file hỗ trợ
```python
supported_extensions = ['.pdf', '.docx', '.xlsx', '.pptx', '.png', '.jpg', '.jpeg', '.doc', '.xls']
```

### 2. Thiết kế bộ chuyển đổi `.doc` bằng `olefile`
```python
class LocalDocConverter(DocumentConverter):
    def accepts(self, file_stream, stream_info, **kwargs):
        return (stream_info.extension or "").lower() == '.doc'

    def convert(self, file_stream, stream_info, **kwargs):
        path = stream_info.local_path
        # ole = olefile.OleFileIO(path)
        # data = ole.openstream('WordDocument').read()
        # decoded = data.decode('utf-16le', errors='ignore')
        # Lọc ký tự tiếng Việt + ASCII printable bằng regex
        # Trả về DocumentConverterResult(markdown=clean_text)
```

### 3. Thiết kế bộ chuyển đổi `.xls` bằng `xlrd`
```python
class LocalXlsConverter(DocumentConverter):
    def accepts(self, file_stream, stream_info, **kwargs):
        return (stream_info.extension or "").lower() == '.xls'

    def convert(self, file_stream, stream_info, **kwargs):
        path = stream_info.local_path
        # workbook = xlrd.open_workbook(path)
        # Duyệt qua các sheets, dòng và cột
        # Format thành bảng Markdown: | Cột 1 | Cột 2 |
        # Trả về DocumentConverterResult(markdown=md_table)
```

### 4. Sửa lỗi `in_biem_mau`
```python
in_biem_mau = bool(re.search(r'\b(form|forms|draft|drafts)\b', rel_path_lower)) or "biểu mẫu" in rel_path_lower
```

## Quy trình Xác minh

### Kiểm thử Thủ công
1. Chạy quét toàn bộ thư mục `1CICTDATA`.
2. Kiểm tra xem các file `.doc` và `.xls` đã được tạo file `.md` trong thư mục `MARKDOWN` hay chưa.
3. Kiểm tra số lượng tài liệu hiển thị trên App SS (Kỳ vọng: tăng từ 264 lên gần 600 - 700 tài liệu).
4. Kiểm thử tìm kiếm các từ khóa đặc trưng trong file `.doc` và `.xls` trên giao diện App.
