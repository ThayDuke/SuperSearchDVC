---
task_name: "Optimize Results UI Title and Badges"
date: "2026-07-02"
version: "v2"
status: "Approved"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Tối ưu hóa tiêu đề và huy hiệu của kết quả tìm kiếm

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> Người dùng muốn tinh chỉnh thêm giao diện kết quả:
> 1. Bỏ tag "Chính thức" (authority badge).
> 2. Bỏ hoàn toàn hiển thị đường dẫn thư mục breadcrumb (`result-breadcrumb`).
> 3. Tên file quá dài sẽ hiển thị trên một dòng duy nhất, cắt phần thừa và thay bằng dấu ba chấm `...`.

## Phạm vi thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo hành vi cốt lõi (Behavioral Memory Anchors)
- Giữ nguyên cấu trúc HTML bên ngoài của card kết quả.
- Giữ nguyên các chức năng tìm kiếm và highlight.

## Kiến trúc giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Cập nhật CSS của `.result-title` trong `SuperSearch.html`
- Thiết lập tiêu đề hiển thị trên một dòng duy nhất, ẩn phần thừa và thêm dấu ba chấm:
  ```css
  .result-title {
      font-size: 0.92rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      flex: 1;
      min-width: 0;
  }
  ```

### 2. Cập nhật JS Render trong `renderResultsList`
- Loại bỏ phần HTML tạo và chèn `.result-breadcrumb`.
- Loại bỏ phần HTML tạo và chèn `authorityBadgeHTML` (tag "Chính thức").

## Kế hoạch xác minh (Verification Plan)

### Kiểm thử thủ công
1. Chạy ứng dụng SuperSearch.exe.
2. Tìm kiếm từ khóa bất kỳ.
3. Xác nhận:
   - Không còn hiển thị tag "Chính thức" màu xanh.
   - Không còn hiển thị đường dẫn thư mục phía trên tiêu đề file.
   - Tiêu đề file có tên dài hiển thị gọn gàng trên 1 dòng kèm dấu `...` ở cuối nếu vượt quá độ rộng của ô kết quả.
