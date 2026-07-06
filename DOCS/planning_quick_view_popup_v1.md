---
task_name: "Quick View Popup Enhancements"
date: "2026-07-02"
version: "v1"
status: "Approved"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Nâng cấp popup xem nhanh nội dung tài liệu

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> Người dùng muốn cải tiến trải nghiệm tương tác với kết quả tìm kiếm và popup xem nhanh:
> 1. Click vào bất kỳ vùng nào của card kết quả cũng đều kích hoạt mở popup xem nhanh (ngoại trừ nút "Đến file gốc").
> 2. Cho phép bôi đen (select) và copy text khi xem nhanh nội dung tài liệu.
> 3. Tăng chiều cao popup tối đa (cách mép trên/dưới khoảng 20px) cho tài liệu dài, và tự động co giãn chiều cao hợp lý đối với tài liệu ngắn. Giữ nguyên chiều ngang để tránh giật giao diện (jitter).

## Phạm vi thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo hành vi cốt lõi (Behavioral Memory Anchors)
- Giữ nguyên cấu trúc thông tin hiển thị bên trong popup (tiêu đề, icon, nội dung văn bản).
- Giữ nguyên chức năng copy path của nút "Đến file gốc".

## Kiến trúc giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Cập nhật CSS trong `SuperSearch.html`
- Thiết lập CSS cho `.modal-body` để cho phép bôi đen chọn văn bản:
  ```css
  .modal-body {
      user-select: text !important;
      -webkit-user-select: text !important;
  }
  ```
- Cập nhật `.quick-view-modal` để tự động co dãn chiều cao theo nội dung nhưng không vượt quá kích thước màn hình (cách mép 20px):
  ```css
  .quick-view-modal {
      height: auto;
      max-height: calc(100vh - 40px);
  }
  ```

### 2. Cập nhật JS trong `renderResultsList`
- Thêm thuộc tính `onclick="openQuickView(${globalIndex})"` và style cursor pointer cho phần tử card kết quả `.result-item`.
- Thêm `event.stopPropagation()` vào thuộc tính `onclick` của nút sao chép "Đến file gốc" để ngăn sự kiện click lan truyền lên card cha.

## Kế hoạch xác minh (Verification Plan)

### Kiểm thử thủ công
1. Chạy ứng dụng SuperSearch.exe.
2. Tìm kiếm từ khóa.
3. Click vào khoảng trống bất kỳ trên card kết quả -> Xác nhận popup xem nhanh mở ra.
4. Click vào nút "Đến file gốc" -> Xác nhận sao chép đường dẫn thành công và popup không bị mở ra.
5. Bôi đen text trong popup -> Xác nhận bôi đen chọn text và copy được bình thường.
6. Xem nhanh tài liệu cực ngắn và cực dài -> Xác nhận popup co giãn chiều cao hợp lý.
