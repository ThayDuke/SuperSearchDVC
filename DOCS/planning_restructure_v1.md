---
task_name: "Gom nhóm file trong thư mục MDBank"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/build.bat"
---

# Kế hoạch dọn dẹp và gom nhóm thư mục MDBank

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> - Giữ lại duy nhất `SuperSearch.exe` và `SuperSearch.html` ở gốc `MDBANK`.
> - Các file khác gom vào thư mục con hợp lý (`data`, `docs`, `logs`, `src`).
> - Đảm bảo ứng dụng tìm kiếm hoạt động bình thường, không bị lỗi nạp dữ liệu.

> [!NOTE]
> **[PHƯƠNG_PHÁP]**
> 1. Sửa mã nguồn `SuperSearch.html` để nạp `data/search_db.js`.
> 2. Sửa mã nguồn `app.py` để ghi `search_db.js` vào `data/` và ghi logs vào `logs/`.
> 3. Di chuyển file `search_db.js` -> `data/`.
> 4. Di chuyển file `MarkItDown guide.md` -> `docs/`.
> 5. Di chuyển file `crash_log.txt` -> `logs/`.
> 6. Tạo thư mục `src/`, di chuyển `app.py`, `copy_libraries.py`, `SuperSearch.spec`, `build.bat`, các file logo `.ico`, và thư mục `Lib/` vào `src/`.
> 7. Cập nhật script `build.bat` bên trong `src/` để build exe xuất ra thư mục cha (`..`).
> 8. Chạy build và chạy thử ứng dụng để kiểm tra hoạt động.

[ĐỀ_XUẤT_TỐI_ƯU]
- Xóa bỏ thư mục build tạm `build` và thư mục `__pycache__` cũ ở gốc để tiết kiệm dung lượng.
- Khi chạy build mới, PyInstaller sẽ tự tạo lại thư mục build tạm bên trong `src/build_temp`.

> [!WARNING]
> **[CẢNH_BÁO]**
> - Nếu di chuyển `search_db.js` mà không sửa HTML và Python, tính năng tìm kiếm sẽ bị hỏng hoàn toàn.
> - Cần cấu hình đúng đường dẫn đầu ra của PyInstaller (`--distpath ..`) để exe mới được ghi đè vào đúng thư mục gốc.

[NEO_HỒI_QUY]
- Thư mục quét tài liệu gốc `MARKDOWN/` và `ORIGINAL/` vẫn nằm ở thư mục gốc `MDBANK/`.
- Thư mục bộ đọc OCR `Tesseract-OCR/` vẫn nằm ở thư mục gốc `MDBANK/`.
- Hai file chạy chính `SuperSearch.exe` và `SuperSearch.html` phải luôn nằm cùng cấp với các thư mục dữ liệu này ở gốc.

---

## Chi tiết các tệp tin tác động (Impact Scope)

- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/app.py)
- [ ] [MODIFY] [build.bat](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/build.bat)
- [ ] [NEW] `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/search_db.js` (Di chuyển từ gốc)
- [ ] [NEW] `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/docs/MarkItDown guide.md` (Di chuyển từ gốc)
- [ ] [NEW] `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/logs/crash_log.txt` (Di chuyển từ gốc)
- [ ] [NEW] `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py` (Di chuyển từ gốc)
- [ ] [NEW] `d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/copy_libraries.py` (Di chuyển từ gốc)
- ... (Các file dev và build khác di chuyển vào `src/`)

---

## Kiến trúc Giải thuật & Mã giả (Pseudocode)

### 1. HTML (`SuperSearch.html`):
```html
<!-- Dòng 1256: Thay đổi đường dẫn nạp JS -->
- <script src="search_db.js"></script>
+ <script src="data/search_db.js"></script>
```

### 2. Python (`app.py`):
```python
# Thay đổi đường dẫn lưu search_db.js
- output_js = os.path.join(self.base_dir, 'search_db.js')
+ output_js = os.path.join(self.base_dir, 'data', 'search_db.js')
+ os.makedirs(os.path.dirname(output_js), exist_ok=True)

# Thay đổi đường dẫn ghi crash_log.txt
- log_path = os.path.join(self.base_dir_exe, "crash_log.txt")
+ log_path = os.path.join(self.base_dir_exe, "logs", "crash_log.txt")
+ os.makedirs(os.path.dirname(log_path), exist_ok=True)
```

### 3. Build script (`build.bat`):
```bat
@echo off
cd /d "%~dp0"
python copy_libraries.py
pyinstaller --distpath .. --workpath build_temp --specpath . --noconfirm SuperSearch.spec
```
