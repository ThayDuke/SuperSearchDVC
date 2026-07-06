---
task_name: "Tách Lib và Tesseract ngoài cho SS"
date: "2026-07-01"
version: "v2"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.spec"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/build.bat"
---

# Kế hoạch Tách thư viện Lib và Tesseract ngoài cho SuperSearch (SS)

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> - Tách các thư viện nặng (markitdown, pdfplumber, pytesseract, PIL, v.v.) vào thư mục `Lib` cục bộ.
> - Đặt thư mục `Tesseract-OCR` cục bộ ở ngoài cạnh tệp thực thi thay vì nén vào trong để giảm dung lượng file chạy SS.
> - Bảo đảm sử dụng đường dẫn tương đối để có thể di động thư mục dự án mà không bị lỗi.
> - Rút gọn kích thước `SuperSearch.exe` xuống dưới 20MB và tăng tốc độ khởi chạy.

## Phạm vi thay đổi
- [ ] [NEW] Tạo thư mục [Lib](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/Lib) chứa các thư viện cài đặt cục bộ.
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/app.py) để nạp động `Lib` vào `sys.path` khi quét.
- [ ] [MODIFY] [SuperSearch.spec](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.spec) loại trừ các module nặng khi đóng gói.
- [ ] [MODIFY] [build.bat](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/build.bat) tự động cài đặt thư viện vào `Lib` trước khi đóng gói.

## Điểm neo hành vi cốt lõi
- Cách thức hoạt động của hai bộ chuyển đổi `LocalOcrPdfConverter` và `LocalOcrImageConverter`.
- Cơ chế quét file, chuyển đổi và ghi đè `search_db.js`.

## Kiến trúc giải thuật & Mã giả (Pseudocode)

### 1. Nạp động thư viện từ thư mục Lib cục bộ trong app.py
```python
# Trong scan_and_index:
# 1. Xác định đường dẫn tương đối tới thư mục Lib nằm cạnh exe
lib_path = os.path.join(base_dir_exe, 'Lib')

# 2. Thêm lib_path vào sys.path để Python có thể import
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# 3. Import động các thư viện nặng
import pytesseract
import pdfplumber
from PIL import Image
from markitdown import MarkItDown
```

### 2. Cấu hình loại trừ thư viện trong SuperSearch.spec
```python
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[], # Loại bỏ Tesseract-OCR và magika khỏi datas trong spec
    hiddenimports=[],
    excludes=[
        'markitdown', 'markitdown_ocr', 'openai', 'magika', 'pdfplumber', 'pdfminer', 
        'pytesseract', 'PIL', 'numpy', 'pandas', 'openpyxl', 'docx', 'pptx', 'matplotlib',
        'jinja2', 'sqlite3', 'tkinter'
    ], # Loại trừ các thư viện này để giảm dung lượng file exe
    ...
)
```

### 3. Tự động cài đặt thư viện vào Lib trong build.bat
```batch
# Tạo thư mục Lib
mkdir Lib
# Cài đặt các thư viện vào Lib bằng cờ -t (target)
pip install markitdown markitdown-ocr pdfplumber pytesseract pillow -t Lib
# Biên dịch exe gọn nhẹ
pyinstaller --distpath . --noconfirm SuperSearch.spec
```

[ĐỀ_XUẤT_TỐI_ƯU]
- Tesseract-OCR và Lib sẽ nằm cạnh file SuperSearch.exe. Khi di chuyển, chỉ cần copy toàn bộ thư mục `MDBANK` là ứng dụng sẽ chạy tốt ở bất kỳ máy tính nào khác mà không cần cài đặt Python.

> [!WARNING]
> **[CẢNH_BÁO]**
> - Khi gọi OCR lần đầu, do phải nạp động các thư viện nặng từ đĩa cứng (Lib) nên quá trình quét file đầu tiên sẽ có độ trễ nhỏ, tuy nhiên tốc độ khởi động giao diện ban đầu của SS sẽ cực kỳ nhanh.

[NEO_HỒI_QUY]
- Giao diện HTML/JS.
- Trình tự quét và phân loại file.

## Kế hoạch kiểm thử thủ công
1. Chạy `build.bat` để cài đặt thư viện vào `Lib` và build exe mới.
2. Xác nhận dung lượng `SuperSearch.exe` mới nằm trong khoảng 15MB - 20MB.
3. Di chuyển/đổi tên thư mục cha của dự án và chạy thử nút "Quét và index" với tài liệu mới để kiểm tra tính di động của đường dẫn tương đối.
