---
task_name: "Adjust Window Size and Notifications style"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Kế hoạch điều chỉnh kích thước cửa sổ và phong cách thông báo SuperSearch

> [!TIP]
> [HIỂU_YÊU_CẦU]
> 1. Khống chế kích thước cửa sổ khởi chạy đạt chuẩn qHD (960x540) và đặt ở giữa màn hình.
> 2. Giới hạn kích thước tối thiểu (min size) cũng là 960x540 để bảo đảm giao diện không bị vỡ.
> 3. Cách hiển thị là crop (responsive), người dùng có thể kéo dãn hoặc maximize lên toàn màn hình bình thường.
> 4. Thông báo quét xong được hiển thị dưới dạng tooltip phong cách Liquid Glass nằm ngay dưới hai nút ở trang chủ, tồn tại 3 giây rồi fadeout.
> 5. Tất cả thông báo alert khác (như lỗi) chuyển sang modal tùy biến Liquid Glass thay thế alert mặc định của trình duyệt.

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên toàn bộ logic quét tài liệu bằng Python (`scan_and_index`).
- Giữ nguyên logic tìm kiếm, xếp hạng và highlight từ khóa.
- Giữ nguyên cơ chế chuyển đổi file và quản lý theme sáng/tối.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Thay đổi kích thước cửa sổ khởi động (app.py)
Thay đổi tham số trong lời gọi `webview.create_window`:
- Cũ: `width=1280, height=800`
- Mới: `width=960, height=540, min_size=(960, 540)`

### 2. Thêm CSS cho Tooltip Liquid Glass (SuperSearch.html)
Thêm lớp CSS `.scan-tooltip` mô phỏng kính mờ:
```css
.scan-tooltip {
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%) translateY(5px);
    background-color: var(--drawer-bg);
    border: 1px solid var(--glass-border);
    backdrop-filter: blur(15px);
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}
.scan-tooltip.show {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) translateY(15px);
}
```

### 3. Tạo Modal Liquid Glass thay thế Alert (SuperSearch.html)
Định nghĩa hàm `showLgAlert(message, title)` và ghi đè `window.alert`:
```javascript
window.alert = function(msg) {
    showLgAlert(msg, "Thông báo");
}
```
Xây dựng thẻ overlay và modal box Liquid Glass trong HTML, xử lý đóng mở và phím bấm tắt (Enter/Esc).

### 4. Logic hiển thị Tooltip Quét xong (SuperSearch.html)
Trong hàm `scanAndIndex()`, thay vì gọi `showToast`, gọi `showScanTooltip` và nâng thời gian `setTimeout(location.reload)` lên 3.5 giây để tooltip hiển thị trọn vẹn 3 giây.

> [!NOTE]
> [PHƯƠNG_PHÁP]
> - Sử dụng CSS Transitions kết hợp thuộc tính `visibility` để tooltip ẩn/hiện mượt mà không gây lỗi giao diện.
> - Override hàm `window.alert` để tất cả cảnh báo lỗi trong ứng dụng tự động hiển thị theo giao diện Liquid Glass.

> [!WARNING]
> [CẢNH_BÁO]
> - Khi đặt kích thước cửa sổ 960x540, cần đảm bảo các nút bấm ở trang chủ không bị tràn hay dính sát lề dưới.
> - Tooltip xuất hiện tuyệt đối không làm dịch chuyển các phần tử khác bên dưới (sử dụng `position: absolute`).

[ĐỀ_XUẤT_TỐI_ƯU]
Việc thay thế `window.alert` toàn cục giúp đồng bộ hóa phong cách Liquid Glass toàn ứng dụng mà không cần sửa đổi hàng loạt lời gọi alert trong mã nguồn cũ.

[NEO_HỒI_QUY]
Cơ chế đóng mở file gốc thông qua API `open_explorer` phải được giữ nguyên hoàn toàn.

## Kế hoạch kiểm thử (Verification Plan)

### Kiểm thử thủ công
1. Khởi động app: Kiểm tra kích thước ban đầu (960x540), kiểm tra vị trí hiển thị giữa màn hình.
2. Thử resize cửa sổ nhỏ hơn 960x540: Xem app có bị chặn thu nhỏ tiếp hay không. Thử maximize cửa sổ xem giao diện có tự giãn dạng crop không.
3. Click "Quét và index" trên app: Kiểm tra tooltip hiển thị bên dưới 2 nút, đợi 3 giây xem có tự biến mất và tải lại trang.
4. Kích hoạt lỗi (ví dụ: chạy file HTML trực tiếp thay vì ứng dụng EXE để gây lỗi kết nối Python): Kiểm tra xem thông báo lỗi hiển thị dưới dạng Modal Liquid Glass thay thế Alert hệ thống.
