---
task_name: "Align Header UI Elements"
date: "2026-07-02"
version: "v1"
status: "Approved"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Căn chỉnh giao diện header kết quả tìm kiếm

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> Người dùng muốn căn chỉnh lại vị trí các thành phần trên header của trang kết quả tìm kiếm:
> 1. Chữ "SuperSearch" (Logo) căn giữa theo Filters Sidebar (rộng 240px).
> 2. Bỏ chức năng click logo để quay lại trang chủ, đổi con trỏ chuột thành default.
> 3. Ô tìm kiếm (Searchbar) căn trái, thẳng hàng với cột hiển thị kết quả (Results Panel).
> 4. Nút chuyển đổi giao diện (Toggle button) căn phải, thẳng hàng với cột hiển thị kết quả.

## Phạm vi thay đổi (Impact Scope)
- [x] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo hành vi cốt lõi (Behavioral Memory Anchors)
- Giữ nguyên cấu trúc DOM hiện tại của `.header-wrapper` và `.search-section`.
- Giữ nguyên chức năng chuyển đổi giao diện (theme toggle) và chức năng tìm kiếm.
- Giữ nguyên thiết kế responsive trên màn hình nhỏ (max-width: 900px).

## Kiến trúc giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Thay đổi CSS trong `SuperSearch.html`
- Cập nhật `.results-state .search-section` để tăng `max-width` từ `600px` lên `800px` (khớp với `.results-panel`).
- Cập nhật `.logo-column` thêm `justify-content: center` để căn giữa logo trong khoảng rộng 240px.
- Cập nhật `.results-state .logo-container` đổi `cursor` từ `pointer` thành `default`.
- Xóa thuộc tính `onclick="resetToHome()"` khỏi logo ở kết quả header.

## Kế hoạch kiểm thử thủ công (Manual Verification)
1. Thực hiện tìm kiếm để chuyển sang giao diện kết quả.
2. Kiểm tra trực quan xem chữ "SuperSearch" có căn giữa so với sidebar bộ lọc hay không.
3. Kiểm tra xem click logo có còn quay về trang chủ không (yêu cầu là KHÔNG còn và con trỏ chuột là default).
4. Kiểm tra xem ô nhập liệu và nút toggle theme có căn lề chính xác theo cột kết quả tìm kiếm không.
