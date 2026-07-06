---
task_name: "Chỉnh sửa hiển thị hàng đợi quét: Khử jitter, thu nhỏ font, phân loại Working/Pending"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Khử Jitter giao diện quét, giảm font size, thêm trạng thái Pending/Working

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> 1. **Khử Jitter:** Khi đang quét, không cho phép sự thay đổi chiều cao của `#progressContainer` hay `#activeFilesList` làm xê dịch logo, thanh tìm kiếm (searchbar) và các nút điều khiển phía trên.
> 2. **Giảm kích thước tên file:** Đổi font-size của tên file trong hàng đợi xử lý xuống 1 size (từ `13px` xuống `12px`).
> 3. **Phân biệt trạng thái:** 
>    - File nào đang thực sự được OCR/chuyển đổi thì hiển thị tag **Working** (màu xanh).
>    - File nào đã nạp vào hàng đợi nhưng chưa đến lượt convert thì hiển thị tag **Pending** (màu xám).

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Giao diện Liquid Glass và các nút điều khiển Pause/Resume/Abort phải giữ nguyên hoạt động bình thường.
- Cơ chế quét đa luồng backend vẫn hoạt động bình thường.

## [PHƯƠNG_PHÁP]

### 1. Khử Jitter (CSS/JS)
- **CSS:** Thêm class `.landing-state.scanning` có thuộc tính `justify-content: flex-start; padding-top: 60px;`.
- **JS:** 
  - Khi bắt đầu quét (`scanAndIndex()`), thêm class `scanning` vào `mainContainer`:
    `document.getElementById("mainContainer").classList.add("scanning");`
  - Khi quét xong hoặc bị hủy (Abort), xóa class này:
    `document.getElementById("mainContainer").classList.remove("scanning");`
  - Nhờ vậy, điểm neo đầu trang (Logo) sẽ đứng im cách đỉnh trang 60px. Các thay đổi về kích thước hàng đợi bên dưới sẽ mở rộng xuống phía dưới trang và không đẩy logo/searchbar lên trên.

### 2. Giảm font size tên file (CSS)
- Cập nhật `.active-file-item` thành `font-size: 12px;` (giảm 1 size so với `13px` hiện tại).

### 3. Phân biệt Working và Pending (Python/JS/CSS)
- **Python Backend (`app.py`):**
  - Thay đổi cấu trúc danh sách `self.active_files` để chứa dictionary: `{"filename": filename, "status": "Pending" | "Working"}`.
  - Khi luồng nhận file mới: Thêm vào danh sách với status là `"Pending"`.
  - Ngay trước khi chạy `md_converter.convert(src_path)`: Cập nhật status của file đó thành `"Working"`.
  - Gửi cấu trúc này lên JS qua `_report_progress()`.
- **JS Frontend (`SuperSearch.html`):**
  - Đọc danh sách cấu trúc mới của `activeFiles`.
  - Khi tạo thẻ item mới, hiển thị tag tương ứng:
    `<span class="active-file-status ${fileObj.status.toLowerCase()}">${fileObj.status}</span>`
- **CSS:**
  - Định nghĩa màu sắc khác biệt cho các tag status:
    - `.active-file-status.working`: Màu xanh sáng (Blue/Teal).
    - `.active-file-status.pending`: Màu xám/bạc (Grey).

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Python (`app.py`)
```python
# Trong run_single_task:
filename = os.path.basename(src_path)

with self.lock:
    # Ban đầu là Pending
    self.active_files.append({"filename": filename, "status": "Pending"})
    active_list = self.active_files[:4]
    percent = int((completed_tasks / total_tasks) * 100)
    self._report_progress(percent, active_list)

success = False
try:
    # Ngay trước khi convert: Cập nhật thành Working
    with self.lock:
        for item in self.active_files:
            if item["filename"] == filename:
                item["status"] = "Working"
                break
        self._report_progress(percent, self.active_files[:4])
        
    result = md_converter.convert(src_path)
    # ...
```

### 2. Frontend CSS (`SuperSearch.html`)
```css
/* Khử jitter */
.landing-state.scanning {
    justify-content: flex-start !important;
    padding-top: 60px !important;
    padding-bottom: 20px !important;
}

/* Giảm 1 size tên file */
.active-file-item {
    font-size: 12px; /* cũ là 13px */
}

/* Tag status */
.active-file-status {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 12px;
    text-transform: uppercase;
}
.active-file-status.working {
    color: var(--accent-blue);
    background: rgba(59, 130, 246, 0.1);
}
.active-file-status.pending {
    color: var(--text-secondary);
    background: rgba(156, 163, 175, 0.15);
}
```

### 3. Frontend JS (`SuperSearch.html`)
```javascript
// Cập nhật updateScanProgress
activeFiles.forEach((fileObj, index) => {
    let file = fileObj.filename;
    let status = fileObj.status; // "Working" hoặc "Pending"
    
    let item = listContainer.querySelector(`.active-file-item[data-filename="${CSS.escape(file)}"]`);
    if (!item) {
        item = document.createElement("div");
        item.className = "active-file-item entering";
        item.setAttribute("data-filename", file);
        item.innerHTML = `
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 80%;" title="${file}">${file}</span>
            <span class="active-file-status ${status.toLowerCase()}">${status}</span>
        `;
        listContainer.appendChild(item);
        // ...
    } else {
        // Cập nhật tag status nếu đổi trạng thái từ Pending sang Working
        const statusSpan = item.querySelector(".active-file-status");
        if (statusSpan) {
            statusSpan.className = `active-file-status ${status.toLowerCase()}`;
            statusSpan.textContent = status;
        }
    }
});
```

## Verification Plan

### Manual Verification
1. Chọn thư mục chứa tối thiểu 5 tài liệu lớn để dễ quan sát.
2. Nhấn "Quét và index".
3. **Xác nhận Khử Jitter:**
   - Quan sát vị trí Logo SuperSearch và ô tìm kiếm ngay khi bắt đầu quét.
   - Logo phải chuyển mượt mà lên trên và đứng yên cố định ở đó. 
   - Khi các file trong hàng đợi thay đổi/cập nhật, logo và ô tìm kiếm không được di chuyển một pixel nào.
4. **Xác nhận font size:**
   - Tên file trong hàng đợi xử lý nhỏ hơn một chút so với trước, hiển thị sắc nét, gọn gàng.
5. **Xác nhận tag status:**
   - Ban đầu khi file mới chèn vào hàng đợi, tag hiển thị là **PENDING** (màu xám).
   - Khi file đó bắt đầu được luồng xử lý chuyển đổi, tag đổi ngay sang **WORKING** (màu xanh dương).
