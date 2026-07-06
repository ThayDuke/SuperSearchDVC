---
task_name: "Optimize Search Results UI"
date: "2026-07-02"
version: "v1"
status: "Approved"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Tối ưu hóa giao diện kết quả tìm kiếm

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> Người dùng muốn thu gọn giao diện kết quả tìm kiếm hơn nữa để tăng mật độ thông tin:
> 1. Ẩn nút "* tài liệu" và "Quét và index" ở kết quả tìm kiếm.
> 2. Đưa nút toggle sáng/tối vào bên phải search bar, giảm chiều cao search bar bằng nút toggle.
> 3. Xóa các filter tag dưới mỗi kết quả.
> 4. Xóa tiền tố đường dẫn `MDBANK\MARKDOWN\...` khỏi breadcrumb.
> 5. Đổi tên nút "Copy Path" thành "Đến file gốc", cấm wrap dòng nút này, cho phép tiêu đề wrap thành 2 dòng khi xung đột.
> 6. Giảm 1 cỡ chữ của tiêu đề kết quả.

## Phạm vi thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo hành vi cốt lõi (Behavioral Memory Anchors)
- Giữ nguyên các chức năng tìm kiếm cơ bản, bao gồm gợi ý từ khóa và highlight thông minh.
- Giữ nguyên logic xử lý chuyển đổi theme.

## Kiến trúc giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Thay đổi cấu trúc HTML trong `SuperSearch.html`
- Di chuyển nút toggle `#themeToggleBtn` ra khỏi thẻ `<header>` và đặt vào bên phải của `.search-box-wrapper` bên trong `.search-section`.
- Di chuyển `<ul id="suggestionsList">` vào bên trong `.search-box-wrapper` để căn chỉnh đúng vị trí của ô nhập liệu.

### 2. Cập nhật CSS của search bar và toggle button
- Thiết lập `.search-section` sử dụng Flexbox để đặt thanh tìm kiếm và nút toggle nằm ngang:
  ```css
  .search-section {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
  }
  ```
- Cho phép `.search-box-wrapper` mở rộng linh hoạt: `flex: 1;`.
- Điều chỉnh chiều cao của `.search-box` xuống `36px` (hoặc `40px` tổng thể) và `.theme-toggle-btn` có chiều cao `40px`.

### 3. Cập nhật JS Render trong `renderResultsList`
- Loại bỏ phần hiển thị của `.result-tags`.
- Cắt bỏ tiền tố `MDBANK/MARKDOWN/` trong chuỗi đường dẫn khi hiển thị breadcrumb.
- Đổi nhãn nút từ `Copy Path` thành `Đến file gốc`.
- Áp dụng CSS `white-space: nowrap; flex-shrink: 0;` cho nút để ngăn xuống dòng.
- Giảm cỡ chữ của tiêu đề kết quả `.result-title` xuống `0.95rem`.

## Kế hoạch xác minh (Verification Plan)

### Kiểm thử thủ công
1. Chạy ứng dụng SuperSearch.exe.
2. Kiểm tra thanh tìm kiếm và nút theme toggle nằm trên cùng một hàng và có chiều cao bằng nhau.
3. Tìm kiếm từ khóa và xác nhận:
   - Các filter tag bên dưới đã biến mất.
   - Đường dẫn breadcrumb không còn chứa `MDBANK › MARKDOWN`.
   - Nút hành động đổi tên thành "Đến file gốc" và hiển thị trên 1 dòng.
   - Cỡ chữ tiêu đề nhỏ gọn hơn.
