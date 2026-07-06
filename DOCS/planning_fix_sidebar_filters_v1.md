---
task_name: "Chỉnh sửa sidebar filter động theo yêu cầu người dùng"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Chỉnh sửa Sidebar Filter Động theo Chủng loại và Thời gian Khởi tạo File

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> Thay đổi các bộ lọc ở sidebar từ cố định thành động theo dữ liệu quét thực tế:
> 1. **LOẠI TÀI LIỆU**: Lọc theo định dạng mở rộng của file gốc (PDF, DOCX, JPG, PNG...), trích xuất động từ `original_path`.
> 2. **NĂM KHỞI TẠO FILE** và **THÁNG KHỞI TẠO FILE**: Lọc theo thời gian khởi tạo/sửa đổi file thực tế trên đĩa (trích xuất qua `os.path.getmtime` từ Python backend và lưu vào database).
> 3. Bỏ các trường lọc nghiệp vụ không có giá trị (`domain`, `language`, `doc_type`).
>
> Điểm tin cậy: 10/10.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [app.py](file:///d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên cấu trúc nạp database tìm kiếm qua file `search_db.js`.
- Giữ nguyên các chức năng cốt lõi của backend (OCR, quét, progress report).
- Giữ nguyên bộ lọc "LỌC KẾT QUẢ" (`filterQuery`).

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> **Bước 1: Cập nhật Python backend (app.py)**
> - Trích xuất thời gian modification time (`mtime`) của `absolute_original_path`.
> - Chuyển đổi thành năm (`file_year`) và tháng (`file_month`) thông qua thư viện `datetime`.
> - Lưu hai trường mới này vào mỗi mục của `SEARCH_DB`.
>
> **Bước 2: Cập nhật Giao diện Frontend (SuperSearch.html)**
> - Đổi các selector biến toàn cục: loại bỏ `selectedDomain`, `selectedLanguage`, `selectedDocType`, `selectedYear`. Thêm `selectedDocExt`, `selectedFileYear`, `selectedFileMonth`.
> - Thay đổi cấu trúc HTML của sidebar filters để chỉ chứa các container: `filterDocExt`, `filterFileYear`, `filterFileMonth` và ô nhập `filterResultsInput`.
> - Cập nhật hàm `renderSidebarFilters()` đếm số lượng định dạng file (trích xuất từ phần mở rộng của `doc.original_path`), `file_year`, và `file_month`.
> - Sửa đổi `renderFilterSection()` để hỗ trợ hiển thị nhãn tháng dạng tiếng Việt (ví dụ: `Tháng 1`, `Tháng 2`...).
> - Cập nhật logic lọc kết quả trong `performSearchFilterAndRender()` khớp với các bộ lọc mới.

[ĐỀ_XUẤT_TỐI_ƯU]
- Việc trích xuất `file_year` và `file_month` trực tiếp từ file gốc qua Python backend là giải pháp an toàn và chuẩn xác nhất.
- Tại Frontend, xử lý fallback nếu thuộc tính `file_year`/`file_month` bị `undefined` (dành cho database cũ chưa quét lại) để đảm bảo không bị lỗi crash giao diện.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Đối với các thư mục tài liệu đã được quét trước đây, file `search_db.js` cũ chưa có trường `file_year`/`file_month`. Do đó, người dùng sẽ cần quét lại thư mục (bấm "Quét và index") để hiển thị thông tin năm/tháng chính xác. Nếu chưa quét lại, giao diện sẽ hiển thị nhãn mặc định là "Không xác định".

[NEO_HỒI_QUY]
- Đảm bảo logic reset filter trong `resetToHome()` và logic nạp lại trang không bị ảnh hưởng.

### Mã giả / Giải thuật đề xuất

#### 1. Cập nhật app.py (trích xuất thời gian khởi tạo file)
```python
# Trong vòng lặp quét file và classify:
file_year = 0
file_month = 0
try:
    if os.path.exists(absolute_original_path):
        import datetime
        mtime = os.path.getmtime(absolute_original_path)
        dt = datetime.datetime.fromtimestamp(mtime)
        file_year = dt.year
        file_month = dt.month
except Exception:
    pass

# Lưu vào db_entries
db_entries.append({
    # ...
    "file_year": file_year,
    "file_month": file_month,
    # ...
})
```

#### 2. Cập nhật bộ lọc sidebar HTML
```html
<div class="filters-sidebar">
    <div class="filter-section">
        <div class="filter-title">Loại Tài Liệu</div>
        <div id="filterDocExt"></div>
    </div>
    <div class="filter-section">
        <div class="filter-title">Năm khởi tạo file</div>
        <div id="filterFileYear"></div>
    </div>
    <div class="filter-section">
        <div class="filter-title">Tháng khởi tạo file</div>
        <div id="filterFileMonth"></div>
    </div>
    <div class="filter-section">
        <div class="filter-title">Lọc kết quả</div>
        <input type="text" class="filter-search-box" id="filterResultsInput" ...>
    </div>
</div>
```

#### 3. Cập nhật logic Javascript trong SuperSearch.html
```javascript
// Biến trạng thái mới
let selectedDocExt = "";
let selectedFileYear = "";
let selectedFileMonth = "";

// Cập nhật performSearchFilterAndRender
if (selectedDocExt) {
    results = results.filter(r => r.original_path.split('.').pop().toUpperCase() === selectedDocExt);
}
if (selectedFileYear) {
    results = results.filter(r => String(r.file_year || r.year || 0) === String(selectedFileYear));
}
if (selectedFileMonth) {
    results = results.filter(r => String(r.file_month || 0) === String(selectedFileMonth));
}
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. Mở SuperSearch.exe, chọn một thư mục chứa nhiều loại file khác nhau (PDF, DOCX, JPG...).
2. Bấm "Quét và index" để cập nhật dữ liệu metadata mới.
3. Tìm kiếm và xác nhận:
   - Sidebar chỉ hiển thị 3 dropdown: "Loại Tài Liệu", "Năm khởi tạo file", "Tháng khởi tạo file" và ô "Lọc kết quả".
   - Dropdown "Loại Tài Liệu" chỉ chứa các chủng loại file quét được (PDF, DOCX...).
   - Lọc thử theo loại tài liệu, năm hoặc tháng và xác nhận kết quả cập nhật chính xác.
