---
task_name: "Cải tiến chọn thư mục: Nhớ trạng thái, nạp động DB, hiệu ứng glow breathing và tối ưu layout"
date: "2026-07-03"
version: "v2"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Cải tiến tính năng chọn thư mục quét tài liệu (V2)

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> 1. **Lưu trạng thái quét:** Sau khi quét/index xong, ghi nhận đường dẫn thư mục và số lượng tài liệu đã quét vào file `data/SSFolder.txt` (dạng JSON).
> 2. **Nạp động & kiểm tra ngay khi chọn folder:** Khi chọn thư mục, kiểm tra xem đã quét chưa:
>    - Nếu rồi: Hiển thị ngay số lượng tài liệu, nạp lại dữ liệu (phục hồi database của folder đó từ bản sao phụ đè lên `search_db.js` và nạp động vào Javascript), tắt hiệu ứng glowing.
>    - Nếu chưa: Hiển thị `0 tài liệu`, gợi ý quét và kích hoạt hiệu ứng glowing thở trên nút quét.
> 3. **Hiệu ứng glowing thở (Breathe Glow):** Nút "Quét và index" có hiệu ứng glowing nhẹ dạng thở đổi màu tuần hoàn (xanh -> lục -> vàng -> đỏ -> tím) nếu thư mục hiện tại chưa được quét.
> 4. **Thay text ở footer:** Chuyển thông tin "Thư mục quét: [đường_dẫn]" xuống footer thay thế cho dòng bản quyền cũ. Ẩn thông tin thư mục ở giữa trang để tối giản UI.
> 5. **Đồng bộ kích thước nút:** Giảm kích thước nút chọn folder (`.circle-btn`) từ 42px xuống 36px để bằng nút toggle sáng tối, căn thẳng hàng.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)
- [ ] [NEW] [SSFolder.txt](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SSFolder.txt) (tự động sinh khi quét xong)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Hàm `scan_and_index()` trong Python cần bảo toàn cấu trúc dữ liệu trả về và quy trình quét đa luồng kết hợp OCR.
- Thay đổi định nghĩa `const SEARCH_DB` trong file sinh ra thành `var SEARCH_DB` để Javascript có thể nạp lại động nhiều lần mà không bị lỗi khai báo lại hằng số của ES6.

## [PHƯƠNG_PHÁP]

### Backend (Python)
1. **Lưu trữ database phụ theo folder:**
   - Sử dụng hàm băm MD5 để tạo tên file database phụ duy nhất cho mỗi folder: `data/search_db_[hash].js`.
   - Trong `scan_and_index()`: Sau khi ghi file `data/search_db.js` chính, sao chép file này thành `data/search_db_[hash].js` của folder vừa quét. Đồng thời ghi nhận thông tin `{normalized_path: doc_count}` vào `data/SSFolder.txt`.
2. **Phục hồi database khi chuyển folder:**
   - Viết hàm `_restore_db_for_folder(folder_path)`:
     - Nếu folder đã quét (tồn tại file database phụ): Copy file phụ đè lên file chính `data/search_db.js`.
     - Nếu chưa quét: Tạo file `data/search_db.js` rỗng chứa `var SEARCH_DB = [];\n`.
   - Gọi hàm phục hồi này trong `load_saved_folder()` and `save_saved_folder()`.
3. **API kiểm tra trạng thái quét:**
   - Viết hàm `check_folder_status(folder_path)` trả về trạng thái quét và số tài liệu từ `data/SSFolder.txt`.

### Frontend (HTML/JS/CSS)
1. **CSS và Hiệu ứng:**
   - Định nghĩa `@keyframes pulseGlow` đổi màu mượt mà tuần hoàn và class `.glow-breathe`.
   - Giảm `.circle-btn` xuống `width: 36px; height: 36px;`.
   - Thêm `align-items: center;` cho `.landing-buttons-row` để căn dọc các nút thẳng hàng.
   - Thêm `display: none !important;` cho `.scan-folder-info` để ẩn nó ở giữa trang.
2. **Footer và Cập nhật UI:**
   - Đổi thẻ `<p>` trong `<footer>` thành `<p id="footerScanFolderText">Thư mục quét: ***</p>`.
   - Hàm `updateFolderUI(path)` sẽ cập nhật trực tiếp vào `#footerScanFolderText`.
3. **Nạp động Database bằng JS:**
   - Viết hàm `reloadSearchDatabase()` để xóa thẻ script cũ và chèn thẻ script `data/search_db.js?t=timestamp` mới, sau đó gọi lại `buildDashboardStats()` và `buildVocabulary()`.
   - Hàm `checkAndRegisterFolderStatus(path)` nhận kết quả từ Python:
     - Nếu đã quét: Gỡ class `.glow-breathe` khỏi nút quét, cập nhật badge số tài liệu, đổi tooltip, và gọi `reloadSearchDatabase()`.
     - Nếu chưa quét: Thêm class `.glow-breathe` vào nút quét, đặt badge về `0 tài liệu`, đổi tooltip gợi ý quét, và làm rỗng mảng `SEARCH_DB` trong bộ nhớ JS.

[ĐỀ_XUẤT_TỐI_ƯU]
- Việc thay đổi `const SEARCH_DB` thành `var SEARCH_DB` trong file sinh ra là giải pháp tốt nhất để tránh lỗi `SyntaxError` khi tải lại script trong môi trường webview mà không cần làm mới (F5) toàn bộ trang.

[CẢNH_BÁO]
- Khi người dùng chọn một folder chưa quét, ta bắt buộc phải ghi đè file `search_db.js` chính bằng mảng rỗng để đảm bảo kết quả tra cứu của folder cũ không bị hiển thị sai lệch.

[NEO_HỒI_QUY]
- Đảm bảo các tiến trình quét vẫn hoạt động độc lập và không ảnh hưởng đến việc tạo chỉ mục khi người dùng nhấn nút "Quét và index".

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Python API (`Api` class trong `app.py`)
```python
def _get_db_filename(self, folder_path):
    normalized = os.path.normpath(folder_path).lower()
    path_hash = hashlib.md5(normalized.encode('utf-8')).hexdigest()
    return f"search_db_{path_hash}.js"

def _restore_db_for_folder(self, folder_path):
    db_dir = os.path.join(self.base_dir, 'data')
    db_filename = self._get_db_filename(folder_path)
    src_db_file = os.path.join(db_dir, db_filename)
    dest_db_file = os.path.join(db_dir, 'search_db.js')
    
    if os.path.exists(src_db_file):
        shutil.copy2(src_db_file, dest_db_file)
        return True
    else:
        with open(dest_db_file, 'w', encoding='utf-8') as f:
            f.write("var SEARCH_DB = [];\n")
        return False

# Thêm hàm check_folder_status
def check_folder_status(self, folder_path=None):
    if not folder_path:
        folder_path = self.scan_dir if self.scan_dir else self.base_dir
    normalized_path = os.path.normpath(folder_path)
    ss_folder_file = os.path.join(self.base_dir, 'data', 'SSFolder.txt')
    if os.path.exists(ss_folder_file):
        with open(ss_folder_file, 'r', encoding='utf-8') as f:
            scanned_dict = json.loads(f.read().strip())
            if normalized_path in scanned_dict:
                return {"scanned": True, "total_entries": scanned_dict[normalized_path]}
    return {"scanned": False}
```

### 2. Frontend JavaScript (`SuperSearch.html`)
```javascript
function reloadSearchDatabase() {
    const oldScript = document.querySelector('script[src^="data/search_db.js"]');
    if (oldScript) oldScript.remove();
    
    const script = document.createElement('script');
    script.src = "data/search_db.js?t=" + new Date().getTime();
    script.onload = function() {
        if (typeof SEARCH_DB !== "undefined") {
            buildDashboardStats();
            buildVocabulary();
            document.getElementById("docCountBtn").textContent = `${SEARCH_DB.length} tài liệu`;
        }
    };
    document.head.appendChild(script);
}

function checkAndRegisterFolderStatus(folderPath) {
    window.pywebview.api.check_folder_status(folderPath).then(function (res) {
        const scanBtn = document.getElementById("scanBtn");
        const docCountBtn = document.getElementById("docCountBtn");
        const tooltipText = document.getElementById("scanTooltipText");
        
        if (res.scanned) {
            scanBtn.classList.remove("glow-breathe");
            docCountBtn.textContent = `${res.total_entries} tài liệu`;
            tooltipText.textContent = "Thư mục đã được quét & index. Sẵn sàng tra cứu!";
            reloadSearchDatabase();
        } else {
            scanBtn.classList.add("glow-breathe");
            docCountBtn.textContent = `0 tài liệu`;
            tooltipText.textContent = "Thư mục chưa được quét. Vui lòng bấm 'Quét và index'.";
            if (typeof SEARCH_DB !== "undefined") {
                SEARCH_DB.length = 0;
                buildDashboardStats();
                buildVocabulary();
            }
        }
    });
}
```

## Verification Plan

### Manual Verification
1. Mở ứng dụng, chọn một thư mục mới hoàn toàn (chưa quét bao giờ).
2. Kiểm tra xem nút "Quét và index" có bắt đầu hiệu ứng glowing "thở" đổi màu hay không.
3. Kiểm tra xem footer có hiển thị đường dẫn thư mục mới chọn hay không. Badge tài liệu hiển thị "0 tài liệu" và tooltip gợi ý quét.
4. Bấm "Quét và index" để quét thư mục. Sau khi quét xong (trang reload), kiểm tra xem hiệu ứng glowing thở đã biến mất, và badge hiển thị đúng số lượng tài liệu đã quét.
5. Kiểm tra file `MDBANK/data/SSFolder.txt` có được cập nhật thông tin thư mục vừa quét cùng số lượng tài liệu chính xác hay không.
6. Chọn lại thư mục mặc định hoặc thư mục đã quét trước đó. Xác nhận ứng dụng hiển thị ngay số lượng tài liệu, nạp đúng database tương ứng (có thể tìm kiếm được ngay) và nút quét không bị glow.
7. Kiểm tra nút chọn folder xem kích thước có bằng nút toggle sáng tối (36px x 36px) và được căn lề thẳng hàng hoàn hảo hay không.
