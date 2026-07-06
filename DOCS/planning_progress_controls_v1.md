---
task_name: "Bổ sung tính năng Pause/Resume và Abort khi quét tài liệu"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Bổ sung tính năng điều khiển tiến trình quét (Pause/Resume, Abort)

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> 1. **Pause/Resume quét:** Cho phép tạm dừng và tiếp tục quá trình quét đa luồng từ giao diện.
> 2. **Abort quét:** Cho phép dừng hẳn quá trình quét. Chỉ xóa duy nhất 1 file `.md` đang quét dở tại luồng bị ngắt. Các file chỉ mục đã hoàn thành trước đó được giữ nguyên vẹn.
> 3. **Quét tiếp tục (Dang dở):** Khi quét lại, tự động bỏ qua các file gốc đã có file chỉ mục `.md` tương ứng ở đích (chức năng này đã có sẵn thông qua kiểm tra sự tồn tại của file `.md`).
> 4. **Giao diện điều khiển:**
>    - Thêm 2 nút: Pause/Play (dùng icon SVG toggle) và Stop (Abort, icon SVG).
>    - Kích thước đúng chuẩn 36px x 36px Liquid Glass (đồng bộ nút toggle sáng tối).
>    - Hiển thị bên cạnh phần trăm tiến trình khi đang quét, tooltip trực quan khi hover.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Cơ chế quét đa luồng sử dụng `ThreadPoolExecutor` phải được giữ nguyên, chỉ bổ sung kiểm soát vòng lặp/tác vụ bằng cờ và sự kiện (`Event`).
- Dữ liệu quét cũ đã hoàn thành của folder phải được giữ nguyên vẹn nếu quá trình quét mới bị hủy bỏ (Abort).

## [PHƯƠNG_PHÁP]

### Backend (Python)
1. **Khởi tạo cờ kiểm soát trong `Api`:**
   - Thêm `self._scan_paused = False` và `self._scan_aborted = False`.
   - Thêm `self._pause_event = threading.Event()` (mặc định `.set()`).
2. **Cập nhật `run_single_task` trong `scan_and_index`:**
   - Trước khi xử lý một file: Kiểm tra `self._scan_aborted` -> thoát ngay; chờ `self._pause_event.wait()` nếu đang pause.
   - Sau khi OCR / Convert: Kiểm tra lại `self._scan_aborted` -> nếu True, hủy ghi file (hoặc xóa file đích nếu đã lỡ ghi) và thoát ngay.
3. **Quản lý kết quả khi hủy (Abort):**
   - Nếu `self._scan_aborted` là True khi kết thúc executor:
     - Bỏ qua dọn dẹp tệp mồ côi.
     - Bỏ qua ghi đè database `search_db.js` chính và phụ.
     - Trả về `{"success": False, "error": "Đã hủy quét"}`.
4. **Viết các hàm API mới:**
   - `pause_scan()`: Đặt pause, gọi `.clear()`.
   - `resume_scan()`: Bỏ pause, gọi `.set()`.
   - `abort_scan()`: Đặt abort, giải phóng pause `.set()` để đánh thức các luồng đang chờ.

### Frontend (HTML/JS/CSS)
1. **CSS nút điều khiển:**
   - Tạo class `.control-btn` có kích thước 36px x 36px với phong cách Liquid Glass giống nút toggle sáng/tối.
2. **HTML thanh tiến trình:**
   - Đưa 2 nút điều khiển vào bên phải tiêu đề tiến trình, nằm trước badge phần trăm hiển thị.
   - Thêm thuộc tính `title` để hiển thị tooltip mặc định của trình duyệt.
3. **Javascript điều khiển:**
   - Viết các hàm `togglePauseResume()` và `abortScan()` gọi API Python tương ứng.
   - Đổi động icon Play/Pause và title tương ứng trạng thái.
   - Disable các nút điều khiển khi bấm Abort để tránh click đúp.
   - Khi quét thất bại/hủy bỏ: Phục hồi giao diện ban đầu, hiển thị tooltip "Đã hủy quét".

[ĐỀ_XUẤT_TỐI_ƯU]
- Việc sử dụng `threading.Event` giúp tạm dừng luồng chạy ngay lập tức ở mức hệ thống mà không gây tốn tài nguyên CPU (no-busy-waiting).

[CẢNH_BÁO]
- Khi bấm Abort, các luồng đang chạy dở OCR (tác vụ nặng) có thể mất vài giây để dừng hẳn. Ta cần vô hiệu hóa nút bấm trên giao diện để tránh người dùng thao tác loạn trong lúc dọn dẹp.

[NEO_HỒI_QUY]
- Đảm bảo khi quét thành công trọn vẹn (không bị Abort), file database và index vẫn được lưu chính xác và trang reload bình thường.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Python API (`app.py`)
```python
# Trong Api.__init__
self._scan_paused = False
self._scan_aborted = False
self._pause_event = threading.Event()
self._pause_event.set()

def pause_scan(self):
    self._scan_paused = True
    self._pause_event.clear()
    return {"success": True}

def resume_scan(self):
    self._scan_paused = False
    self._pause_event.set()
    return {"success": True}

def abort_scan(self):
    self._scan_aborted = True
    self._pause_event.set() # Đánh thức các luồng đang ngủ
    return {"success": True}

# Trong scan_and_index
def scan_and_index(self):
    self._scan_paused = False
    self._scan_aborted = False
    self._pause_event.set()
    # ...
    
    def run_single_task(task):
        if self._scan_aborted:
            return
            
        self._pause_event.wait() # Chờ nếu tạm dừng
        
        if self._scan_aborted:
            return
            
        # ... convert file ...
        # ... ghi file dest_md_path ...
        
        if self._scan_aborted:
            # Xóa file dở dang lập tức
            if os.path.exists(dest_md_path):
                os.remove(dest_md_path)
            return
```

### 2. Frontend JavaScript & HTML (`SuperSearch.html`)
```html
<!-- HTML trong #progressContainer -->
<div class="progress-header-row">
    <span class="progress-title" id="progressTitleText">Đang quét tài liệu...</span>
    <div class="progress-controls-row">
        <button id="pauseResumeBtn" class="control-btn" onclick="togglePauseResume()" title="Tạm dừng quét">
            <svg id="pauseIcon" ...><rect ...></rect></svg>
            <svg id="playIcon" style="display:none;" ...><polygon ...></polygon></svg>
        </button>
        <button id="abortBtn" class="control-btn" onclick="abortScan()" title="Hủy bỏ quét">
            <svg ...><rect ...></rect></svg>
        </button>
        <span id="progressPercentText" class="progress-percent">0%</span>
    </div>
</div>
```

```javascript
let isPaused = false;

function togglePauseResume() {
    const pauseIcon = document.getElementById("pauseIcon");
    const playIcon = document.getElementById("playIcon");
    const btn = document.getElementById("pauseResumeBtn");
    const title = document.getElementById("progressTitleText");
    
    if (!isPaused) {
        window.pywebview.api.pause_scan().then(function() {
            isPaused = true;
            pauseIcon.style.display = "none";
            playIcon.style.display = "block";
            btn.title = "Tiếp tục quét";
            title.textContent = "Đang tạm dừng quét...";
        });
    } else {
        window.pywebview.api.resume_scan().then(function() {
            isPaused = false;
            pauseIcon.style.display = "block";
            playIcon.style.display = "none";
            btn.title = "Tạm dừng quét";
            title.textContent = "Đang quét tài liệu...";
        });
    }
}

function abortScan() {
    document.getElementById("abortBtn").disabled = true;
    document.getElementById("pauseResumeBtn").disabled = true;
    document.getElementById("progressTitleText").textContent = "Đang hủy bỏ quét...";
    window.pywebview.api.abort_scan();
}
```

## Verification Plan

### Manual Verification
1. Chuẩn bị một thư mục quét lớn (chứa nhiều file PDF/Image để tiến trình chạy đủ lâu).
2. Nhấn "Quét và index".
3. **Test Pause/Resume:** 
   - Nhấn nút "Tạm dừng quét" (Pause). Xác nhận tiêu đề tiến trình chuyển thành "Đang tạm dừng quét...", icon đổi sang Play, và phần trăm tiến trình dừng tăng.
   - Nhấn "Tiếp tục quét" (Play). Tiến trình quét phải tiếp tục chạy bình thường.
4. **Test Abort:**
   - Khi đang quét, nhấn nút "Hủy bỏ quét" (Stop).
   - Xác nhận:
     - Giao diện phục hồi lại màn hình ban đầu sau khi hủy xong.
     - Kiểm tra trong thư mục `MARKDOWN` cục bộ: Các file đang quét dở dang (chưa hoàn thành trước lúc bấm Stop) phải bị xóa sạch khỏi thư mục, không có file rác bị lưu lại.
5. **Test Quét tiếp tục:**
   - Chạy lại quét lần thứ 2 cho cùng thư mục đó.
   - Xác nhận: Tiến trình quét sẽ bỏ qua các file đã được quét thành công từ lần 1 và chạy cực nhanh đối với các file đó.
