---
task_name: "Xử lý lỗi convert nhầm ký tự tiếng Trung cho file .doc"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
---

# Kế hoạch sửa lỗi convert nhầm ký tự tiếng Trung (Mojibake)

> [!TIP]
> ### [HIỂU_YÊU_CẦU] (Confidence Score: 10/10)
> 1. **Hiện tượng:** Khi chạy convert file `.doc` sang `.md`, văn bản tiếng Anh/Việt bị biến thành ký tự tiếng Trung rác.
> 2. **Nguyên nhân:**
>    - Định dạng `.doc` nhị phân cũ chứa văn bản 1-byte (ASCII/ANSI) bị `LocalDocConverter` decode cưỡng ép bằng `utf-16le`, dẫn đến cứ 2 byte liền kề bị ghép nhầm thành 1 ký tự tiếng Trung CJK.
>    - Bộ lọc regex cũ dùng class `\w` để khớp chữ cái, nhưng `\w` trong Unicode khớp cả ký tự tiếng Trung. Dẫn đến giữ lại toàn bộ rác nhị phân và rác ghép sai byte.
> 3. **Mục tiêu:**
>    - Khôi phục chuẩn xác ký tự 1-byte bị ghép nhầm trong UTF-16LE.
>    - Thắt chặt regex bộ lọc để chỉ khớp tiếng Việt, tiếng Anh và ký tự đặc biệt thông dụng, loại bỏ hoàn toàn dải ký tự tiếng Trung.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py) (Dòng 644-705: cập nhật class `LocalDocConverter`)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Giữ nguyên kiến trúc kế thừa `DocumentConverter` của `LocalDocConverter`.
- Giữ nguyên các định dạng trả về và xử lý lỗi ngoại lệ trong phương thức `convert()`.

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> 1. **Mở rộng dải byte khôi phục:**
>    - Cập nhật `valid_bytes` trong logic khôi phục ký tự 1-byte để nhận diện toàn bộ các ký tự in được (byte từ 32 đến 255) cộng với tab/newline.
> 2. **Thắt chặt regex lọc chữ:**
>    - Định nghĩa một regex tường minh chỉ bao gồm ký tự Latin/ASCII, ký tự tiếng Việt dựng sẵn và tổ hợp có dấu, cùng các dấu câu phổ biến.
>    - Thay thế hoàn toàn `\w` để ngăn chặn việc khớp các ký tự tiếng Trung sinh ra từ dữ liệu nhị phân rác.

[ĐỀ_XUẤT_TỐI_ƯU]
- Giải pháp này can thiệp trực tiếp vào regex và logic decode mà không cần cài đặt thêm bất kỳ thư viện ngoài nào (như pywin32 hay antiword), đảm bảo hiệu năng tối ưu và tính độc lập của ứng dụng SuperSearch.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Do regex bị thắt chặt, cần đảm bảo không bỏ sót các ký tự tiếng Việt có dấu lạ hoặc ký tự đặc biệt cần thiết cho tài liệu. Dải ký tự tiếng Việt đã được liệt kê đầy đủ.

[NEO_HỒI_QUY]
- Đảm bảo logic fallback sang Latin-1 khi văn bản trích xuất quá ngắn vẫn hoạt động đúng với regex mới.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Cập nhật `LocalDocConverter` trong [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

```python
class LocalDocConverter(DocumentConverter):
    # ... accepts ...
    
    def convert(self, file_stream, stream_info, **kwargs):
        # ... Đọc stream WordDocument ...
        # decoded_utf16 = data.decode('utf-16le', errors='ignore')
        
        # 1. Khôi phục ký tự 1-byte bị ghép nhầm
        # valid_bytes = {9, 10, 13} | set(range(32, 256))
        # Duyệt qua decoded_utf16, rã ký tự > 255 thành 2 byte nếu cả 2 byte nằm trong valid_bytes.
        
        # 2. Lọc văn bản bằng regex tiếng Việt/tiếng Anh nghiêm ngặt
        # vietnamese_and_english_chars = r'[a-zA-Z0-9ÀÁÂ...-–—,.?\/()\'"“”‘’+:;!@#%&*=_ \t\n\r]'
        # pattern = re.compile(vietnamese_and_english_chars + r'{4,}')
        # matches = pattern.findall(decoded_utf16)
        # clean_chunks = ...
        # full_text = "\n\n".join(clean_chunks)
        
        # 3. Fallback sang latin-1 nếu độ dài quá ngắn
        # ...
```
