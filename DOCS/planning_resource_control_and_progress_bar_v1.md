---
task_name: "Kiểm soát tài nguyên và Thanh tiến trình Liquid Glass"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Kế hoạch Kiểm soát tài nguyên & Thanh tiến trình Liquid Glass

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> - Khống chế tài nguyên chạy đa luồng (CPU & RAM < 70%).
> - Bổ sung thanh tiến trình (Progress Bar) Liquid Glass đẹp mắt.
> - Hiển thị danh sách file đang quét (tối đa 3 file rõ, file thứ 4 làm mờ dần ở dưới).
> - Tự động cập nhật giao diện thời gian thực qua pywebview.
> - Điểm tin cậy: 10/10.

## Phạm vi thay đổi

- [ ] [MODIFY] [app.py](file:///d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi
- Logic OCR của `LocalOcrPdfConverter` và `LocalOcrImageConverter` giữ nguyên.
- Cấu trúc file xuất ra trong `MARKDOWN` và cơ sở dữ liệu `search_db.js`.

---

## Kiến trúc Giải thuật & Mã giả (Pseudocode)

### 1. Kiểm soát tài nguyên trong app.py

```python
import ctypes
import os
from concurrent.futures import ThreadPoolExecutor
import threading

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_uint64),
        # ... các trường khác của struct GlobalMemoryStatusEx
    ]

class Api:
    def __init__(self, base_dir):
        # ... giữ nguyên khởi tạo
        self.window = None
        self.active_files = set()
        self.lock = threading.Lock()

    def set_window(self, window):
        self.window = window

    def get_system_ram_load(self):
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.dwMemoryLoad

    def get_safe_workers_count(self):
        cpu_cores = os.cpu_count() or 4
        # Giới hạn 70% số nhân CPU
        max_cpu_workers = max(1, int(cpu_cores * 0.7))
        
        # Kiểm tra RAM hiện tại
        ram_load = self.get_system_ram_load()
        if ram_load > 70:
            # RAM hệ thống đã trên 70%, chỉ dùng 1 luồng để tránh treo máy
            return 1
        return max_cpu_workers
```

### 2. Luồng quét đa luồng cập nhật tiến trình

```python
    def scan_and_index(self):
        # 1. Tìm tất cả các file cần convert
        files_to_convert = []
        # Duyệt và lập danh sách file cần OCR (giống logic cũ nhưng gom danh sách trước)
        
        total_files = len(files_to_convert)
        if total_files == 0:
            # Gửi tiến trình 100%
            self.report_progress(100, [])
            return self.finalize_indexing()

        completed_count = 0
        workers = self.get_safe_workers_count()

        def process_single_file(file_path):
            nonlocal completed_count
            filename = os.path.basename(file_path)
            
            # Thêm vào danh sách đang chạy
            with self.lock:
                self.active_files.add(filename)
                # Lấy danh sách tối đa 4 file để truyền xuống front-end
                active_list = list(self.active_files)[:4]
                percent = int((completed_count / total_files) * 100)
                self.report_progress(percent, active_list)

            # --- Thực hiện chuyển đổi và lưu file (OCR) ---
            try:
                # convert_logic(file_path)
                pass
            except Exception:
                pass

            # Xóa khỏi danh sách đang chạy
            with self.lock:
                self.active_files.discard(filename)
                completed_count += 1
                percent = int((completed_count / total_files) * 100)
                active_list = list(self.active_files)[:4]
                self.report_progress(percent, active_list)

        # Chạy đa luồng an toàn bằng ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as executor:
            executor.map(process_single_file, files_to_convert)

        # 2. Cập nhật file search_db.js
        return self.finalize_indexing()

    def report_progress(self, percent, active_list):
        if self.window:
            files_json = json.dumps(active_list)
            self.window.evaluate_js(f"updateScanProgress({percent}, {files_json})")
```

### 3. Giao diện hiển thị trong SuperSearch.html

```html
<!-- Bảng tiến trình Liquid Glass (mặc định ẩn) -->
<div id="progressContainer" class="progress-panel-wrapper" style="display: none;">
    <div class="progress-bar-track">
        <div id="progressBarFill" class="progress-bar-fill"></div>
    </div>
    <div class="progress-info">
        <span id="progressPercentText">0%</span>
        <button id="toggleActiveFilesBtn" class="circle-toggle-btn">
            <svg class="chevron-icon" viewBox="0 0 24 24">
                <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
            </svg>
        </button>
    </div>
    <!-- Danh sách file đang xử lý -->
    <div id="activeFilesList" class="active-files-list"></div>
</div>
```

```css
/* CSS Liquid Glass & hiệu ứng mờ dần */
.progress-panel-wrapper {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    backdrop-filter: blur(20px);
    border-radius: var(--radius-inner);
    padding: 20px;
    box-shadow: var(--card-shadow);
}
.progress-bar-track {
    width: 100%;
    height: 8px;
    background: rgba(0, 0, 0, 0.05);
    border-radius: 4px;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple), var(--accent-pink));
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.circle-toggle-btn {
    border-radius: 50%;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    cursor: pointer;
    transition: var(--transition-snappy);
}
.circle-toggle-btn.open .chevron-icon {
    transform: rotate(180deg);
}
.active-file-item.faded-bottom {
    opacity: 0.4;
    mask-image: linear-gradient(to bottom, black 0%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, black 0%, transparent 100%);
}
```

```javascript
// Hàm Javascript nhận dữ liệu từ Python
function updateScanProgress(percent, activeFiles) {
    document.getElementById("progressBarFill").style.width = percent + "%";
    document.getElementById("progressPercentText").textContent = percent + "%";
    
    const listContainer = document.getElementById("activeFilesList");
    listContainer.innerHTML = "";
    
    activeFiles.forEach((filename, index) => {
        const item = document.createElement("div");
        item.className = "active-file-item";
        if (index === 3) {
            // File thứ 4 bị làm mờ nửa dưới
            item.className += " faded-bottom";
        }
        item.textContent = `${filename}: working`;
        listContainer.appendChild(item);
    });
}
```

---

## [ĐỀ_XUẤT_TỐI_ƯU]
- Dùng ThreadPoolExecutor thay vì ProcessPoolExecutor để tránh chi phí nạp lại toàn bộ module khi đóng gói bằng PyInstaller.
- Sử dụng hàm GlobalMemoryStatusEx thông qua ctypes của Windows giúp không cần cài đặt thêm thư viện psutil.

> [!WARNING]
> **[CẢNH_BÁO]**
> - Nếu file PDF gốc quá lớn (ví dụ hàng trăm trang), Poppler render ra ảnh có thể chiếm dung lượng RAM đột biến, cần kiểm soát kỹ lượng trang được xử lý song song.

[NEO_HỒI_QUY]
- Giữ nguyên cơ chế phân loại danh mục, phát hiện ngôn ngữ, ghi search_db.js.

---

## Kế hoạch kiểm thử thủ công
1. Đưa 5-10 file PDF/Ảnh chưa được OCR vào thư mục MDBANK.
2. Bấm nút "Quét và index".
3. Kiểm tra xem Progress Bar có xuất hiện và thanh tiến trình có tăng dần từ 0% tới 100% mượt mà không.
4. Bấm nút tròn mũi tên xuống dưới để kiểm tra danh sách file đang xử lý:
   - Xác nhận tối đa hiển thị 4 file.
   - Xác nhận file thứ 4 bị làm mờ nửa dưới.
   - Xác nhận khi file hoàn thành biến mất, các file khác đẩy lên.
