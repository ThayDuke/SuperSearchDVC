---
task_name: "Bổ sung tính năng chọn thư mục quét tài liệu"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Bổ sung nút chọn thư mục quét tài liệu tùy chỉnh

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Thêm 1 nút tròn có chứa icon SVG thư mục (đơn sắc), hover hiện hint "Chọn thư mục tài liệu để quét".
> - Nút tròn và các thông báo/dialog phát sinh cần tuân thủ giao diện Liquid Glass.
> - Bấm nút mở hộp thoại cho phép chọn thư mục quét từ hệ thống (select folder).
> - Lưu đường dẫn đã chọn vào file `data/folder_path.txt` (nằm cạnh `search_db.js`).
> - Khi khởi động ứng dụng, tự động tải lại đường dẫn đã lưu từ file cấu hình.
> - Nếu chọn thư mục mới, ghi đè đường dẫn cũ để đảm bảo chỉ quét duy nhất 1 thư mục gốc (và các con của nó).
> - Khi bấm "Quét và index":
>   - Nếu chưa chọn thư mục, quét thư mục mặc định (nơi đặt ứng dụng `SS.exe`).
>   - Nếu đã chọn thư mục, quét thư mục được chọn.
> - Đảm bảo dọn dẹp các tệp `.md` thừa từ thư mục quét khác trong đợt quét mới để tránh lẫn lộn kết quả tìm kiếm.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)
- [ ] [NEW] [folder_path.txt](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/folder_path.txt) (tự động sinh khi chọn thư mục)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Hàm `scan_and_index()` trong Python cần bảo toàn khả năng convert đa luồng, hỗ trợ OCR PDF/Hình ảnh và các bộ phân loại document type, domain, language, year như hiện tại.
- Định dạng cơ sở dữ liệu `search_db.js` với các trường `title`, `path`, `original_path`, `absolute_original_path`, `domain`, `doc_type`, `language`, `year`, `content` không được thay đổi cấu trúc để tránh lỗi đọc ở Frontend.

## [PHƯƠNG_PHÁP]
> [!NOTE]
> ### Backend (Python)
> 1. Trong khởi tạo class `Api`:
>    - Thêm biến lưu trữ thư mục quét `self.scan_dir = None`.
>    - Tự động load giá trị từ `data/folder_path.txt` nếu file tồn tại và đường dẫn hợp lệ.
> 2. Viết thêm hai hàm API để giao tiếp với Frontend:
>    - `select_folder()`: Gọi `self._window.create_file_dialog(webview.FOLDER_DIALOG)`. Khi có kết quả hợp lệ, chuẩn hóa đường dẫn, ghi đè vào `data/folder_path.txt`, gán cho `self.scan_dir` và trả về kết quả.
>    - `get_scan_folder()`: Trả về thư mục quét hiện tại và thư mục mặc định (`self.base_dir`).
> 3. Tối ưu hóa logic quét trong `scan_and_index()`:
>    - Xác định `scan_target = self.scan_dir if self.scan_dir else self.base_dir`.
>    - Nếu `scan_target` là `self.base_dir`: Giữ nguyên logic di chuyển file gốc vào `ORIGINAL` và convert file `.md` vào `MARKDOWN`.
>    - Nếu `scan_target` khác `self.base_dir` (thư mục ngoài của user):
>      - Quét toàn bộ file hợp lệ trong `scan_target`.
>      - Không di chuyển file gốc, chỉ convert và xuất file `.md` tương ứng vào `MARKDOWN` (giữ nguyên cấu trúc thư mục con).
>      - Ghi nhận `absolute_original_path` trỏ trực tiếp đến file gốc ở thư mục ngoài.
>    - Thực hiện quy trình "Dọn dẹp tệp tin mồ côi": thu thập tất cả các file `.md` đích dự kiến của đợt quét này. Duyệt qua `MARKDOWN` và xóa các file `.md` cũ/không liên quan đến thư mục quét hiện tại để bảo đảm dữ liệu ghi đè sạch sẽ.
>
> ### Frontend (HTML/JS/CSS)
> 1. Thiết kế CSS Liquid Glass cho nút tròn chọn thư mục (`.circle-btn`) và khu vực hiển thị thông tin thư mục hiện tại (`.scan-folder-info`) với các hiệu ứng hover, shadow, blur và highlight mượt mà.
> 2. Đưa nút chọn thư mục nằm bên phải nút "Quét và index".
> 3. Hiển thị một badge nhỏ bên dưới thông tin thư mục đang được chọn.
> 4. Viết hàm Javascript:
>    - `selectFolder()`: Gọi API Python để chọn thư mục, hiển thị thông báo Modal Liquid Glass và cập nhật giao diện.
>    - `initFolderConfig()`: Nạp thông tin thư mục đã lưu khi khởi chạy trang.
>    - `updateFolderUI(path)`: Cập nhật văn bản hiển thị thư mục đang quét.

[ĐỀ_XUẤT_TỐI_ƯU]
- Lưu cache file `.md` thay vì xóa sạch toàn bộ `MARKDOWN` mỗi khi quét để giúp tăng tốc các lần quét sau đối với cùng thư mục. Cơ chế so sánh danh sách file đích mong muốn (`expected_markdown_files`) sẽ tự động xóa các file rác mà không cần xóa trắng cache.
- Sử dụng dialog chọn thư mục của pywebview thông qua `window.create_file_dialog(webview.FOLDER_DIALOG)` giúp giao diện đồng bộ với OS của người dùng mà không cần cài đặt thêm thư viện ngoài.

[CẢNH_BÁO]
> [!WARNING]
> - Tuyệt đối không di chuyển hoặc xóa các file gốc nằm ở thư mục tùy chọn bên ngoài của người dùng.
> - Cần loại trừ các thư mục đặc biệt (`.git`, `__pycache__`, `node_modules`...) khi người dùng chọn quét một thư mục ngoài lớn để tránh tràn bộ nhớ hoặc quét nhầm các file code/hệ thống.

[NEO_HỒI_QUY]
- Đảm bảo cơ chế mở file gốc bằng Windows Explorer (`open_explorer`) vẫn hoạt động bình thường bằng cách cung cấp chính xác `absolute_original_path` cho cả hai chế độ quét (mặc định và tùy chọn).

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Python API (`Api` class trong `app.py`)
```python
# Biến lưu trữ scan_dir trong Api.__init__
self.scan_dir = None
self.load_saved_folder()

# Hàm load thư mục đã lưu
def load_saved_folder(self):
    path_file = os.path.join(self.base_dir, 'data', 'folder_path.txt')
    if os.path.exists(path_file):
        path = read_file(path_file)
        if os.path.exists(path):
            self.scan_dir = path

# Hàm lưu thư mục
def save_saved_folder(self, path):
    path_file = os.path.join(self.base_dir, 'data', 'folder_path.txt')
    write_file(path_file, path)
    self.scan_dir = path

# API chọn thư mục cho frontend
def select_folder(self):
    result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
    if result:
        self.save_saved_folder(result[0])
        return {"success": True, "folder_path": result[0]}
    return {"success": False, "error": "Đã hủy chọn thư mục"}

# API lấy thông tin thư mục
def get_scan_folder(self):
    return {"folder_path": self.scan_dir or ""}
```

### 2. Logic Quét và Index cải tiến trong Python
```python
def scan_and_index(self):
    scan_target = self.scan_dir if self.scan_dir else self.base_dir
    expected_markdown_files = set()
    
    # 1. Thu thập tệp nguồn & tạo tác vụ convert
    if scan_target == self.base_dir:
        # Quét thư mục gốc mặc định (logic cũ có di chuyển vào ORIGINAL)
        # Thêm các file ở base_dir ngoài và ORIGINAL vào expected_markdown_files
        ...
    else:
        # Quét thư mục ngoài tùy chọn (không di chuyển gốc)
        for root, dirs, files in os.walk(scan_target):
            # Bỏ qua thư mục hệ thống/code
            ...
            for file in files:
                if file is supported:
                    rel_dir = os.path.relpath(root, scan_target)
                    expected_md_path = os.path.join(markdown_root, rel_dir, file + ".md")
                    expected_markdown_files.add(expected_md_path)
                    
                    if expected_md_path not in exists:
                        tasks.append(convert_task(file_path, expected_md_path, clean=False))
                        
    # 2. Thực thi convert đa luồng (như cũ)
    ...
    
    # 3. Dọn dẹp các tệp .md không còn tồn tại trong đợt quét này (orphaned files)
    for root, dirs, files in os.walk(markdown_root):
        for file in files:
            md_path = os.path.join(root, file)
            if md_path not in expected_markdown_files:
                os.remove(md_path)
                
    # 4. Ghi cơ sở dữ liệu search_db.js
    # Duyệt qua markdown_root, xác định file gốc tương ứng dựa trên cấu trúc thư mục
    # - Nếu quét mặc định: file gốc tương ứng trong ORIGINAL/rel_dir/
    # - Nếu quét tùy chỉnh: file gốc tương ứng trong scan_target/rel_dir/
    ...
```

### 3. Frontend JS & HTML
```javascript
// Thêm nút folderBtn bên cạnh scanBtn
// Khi window nạp, gọi initFolderConfig() để cập nhật giao diện
// Khi bấm folderBtn: gọi selectFolder() -> showLgAlert báo thành công -> cập nhật thẻ #currentScanFolderText
```

## Verification Plan

### Manual Verification
1. Khởi chạy ứng dụng `SuperSearch`, kiểm tra xem giao diện có hiển thị nút tròn chọn thư mục và dòng thông tin "Thư mục quét: Mặc định" hay không.
2. Di chuột lên nút chọn thư mục, xác nhận hint "Chọn thư mục tài liệu để quét" hiển thị đúng.
3. Bấm vào nút chọn thư mục, hộp thoại hệ thống mở ra. Chọn một thư mục chứa tài liệu test bên ngoài ổ đĩa khác.
4. Xác nhận hộp thoại Modal Liquid Glass hiển thị báo thành công và thông tin thư mục quét chuyển sang đường dẫn vừa chọn.
5. Kiểm tra file `MDBANK/data/folder_path.txt` được tạo và chứa đúng đường dẫn đó.
6. Tắt ứng dụng và mở lại, kiểm tra xem ứng dụng có tự động nạp lại thư mục quét đã chọn từ trước hay không.
7. Bấm "Quét và index" thư mục tùy chỉnh đó. Kiểm tra xem các file `.md` được sinh ra trong `MARKDOWN` và file gốc của bạn không bị di chuyển hay biến mất khỏi thư mục gốc.
8. Tìm kiếm thử một từ khóa trong tài liệu ở thư mục tùy chỉnh đó, bấm "Đến file gốc" và kiểm tra xem Explorer có mở đúng vị trí file gốc bên ngoài không.
9. Đổi lại thư mục quét khác (hoặc xóa file `folder_path.txt`), quét lại và kiểm tra xem các chỉ mục cũ có bị dọn dẹp sạch khỏi `search_db.js` hay không.
