---
task_name: "Tối ưu hiển thị hàng đợi và hiệu ứng trượt Liquid Glass"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Tối ưu hiển thị hàng đợi và hiệu ứng trượt Liquid Glass

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> - Hiển thị hàng đợi theo thứ tự FIFO (file đang xử lý xếp số 1).
> - File hoàn thành biến mất trước, các file sau dồn lên trên.
> - Hiệu ứng trượt mở rộng/thu gọn danh sách mượt mà (Liquid Glass style).
> - Hiệu ứng trượt dồn hàng lên trên khi file trước biến mất.
> - Điểm tin cậy: 10/10.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Logic đa luồng xử lý chuyển đổi file trong `app.py`.
- Cơ chế gửi tiến trình `_report_progress` từ Python xuống JS.
- Các API Python được expose sang JS qua lớp `Api`.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> **[PHƯƠNG_PHÁP]**

### 1. Phía Python (app.py)
- Chuyển `self.active_files` từ dạng `set()` sang `list()` để giữ thứ tự FIFO.
- Khi bắt đầu xử lý task, dùng `self.active_files.append(filename)`.
- Khi xử lý xong task, dùng `self.active_files.remove(filename)` (bọc trong khối an toàn luồng).

### 2. Phía Giao diện CSS (SuperSearch.html)
- Thay đổi thuộc tính `.active-files-list` để hỗ trợ transition:
  - Mặc định: `max-height: 0`, `opacity: 0`, `overflow: hidden`, `padding: 0`, `transition: max-height 0.5s, opacity 0.4s`.
  - Khi có class `.show`: `max-height: 200px`, `opacity: 1`, `padding-top: 8px`, `border-top: 1px dashed`.
- Thêm class `.entering` và `.exit` cho `.active-file-item` để hỗ trợ trượt mượt mà:
  - `.entering` và `.exit` sẽ giảm `max-height`, `opacity`, `padding`, `margin` về 0 để tạo hiệu ứng thu hẹp / mở rộng mượt.

### 3. Phía JS Logic (SuperSearch.html)
- Thay đổi hàm `updateScanProgress(percent, activeFiles)`:
  - Sử dụng DOM Diffing đơn giản dựa trên attribute `data-filename` của các item.
  - File biến mất khỏi `activeFiles` mới -> Thêm class `.exit` cho DOM node cũ, sau đó `removeChild` sau 400ms.
  - File mới xuất hiện -> Tạo DOM node mới với class `.entering`, chèn vào container, sau đó bỏ class `.entering` để tạo hiệu ứng mở rộng mượt.
  - Chỉ dọn dẹp hoặc vẽ lại hoàn toàn khi `activeFiles` trống.

**[ĐỀ_XUẤT_TỐI_ƯU]**
- Tần suất cập nhật UI từ Python gửi xuống JS là theo mỗi file hoàn thành hoặc bắt đầu. Việc dùng transition 400ms là phù hợp để các hiệu ứng không bị chồng chéo quá nhanh gây giật lag.

> [!WARNING]
> **[CẢNH_BÁO]**
> - Xử lý đa luồng trong Python có thể gọi append/remove đồng thời, bắt buộc phải bảo vệ bằng `self.lock`.
> - Việc sử dụng `requestAnimationFrame` trong JS là cần thiết để trình duyệt kịp cập nhật trạng thái ban đầu của class `.entering`.

**[NEO_HỒI_QUY]**
- Đảm bảo thanh tiến trình phần trăm (`progressBarFill`) hoạt động chính xác.
- Đảm bảo khi hoàn thành 100%, hàng đợi tự động dọn dẹp an toàn.
