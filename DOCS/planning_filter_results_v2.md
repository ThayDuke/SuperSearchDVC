---
task_name: "Tối ưu hóa bộ lọc trong kết quả"
date: "2026-07-02"
version: "v2"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Tối ưu hóa bộ lọc kết quả và cải thiện hiệu năng

Giải quyết vấn đề sắp xếp kết quả liên quan khi dùng bộ lọc phụ và giảm giật lag bằng cách kích hoạt lọc khi nhấn Enter.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- `executeSearch`: Reset trạng thái bộ lọc phụ khi gõ tìm kiếm chính mới.
- `resetToHome`: Reset giá trị ô lọc và từ khóa lọc.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Thay đổi sự kiện ô Lọc kết quả sang KeyDown (Enter)
Trong HTML:
```html
<input type="text" class="filter-search-box" id="filterResultsInput" placeholder="Gõ từ khóa cần lọc" onkeydown="handleFilterResultsKeyDown(event)">
```

Trong JavaScript:
```javascript
function handleFilterResultsKeyDown(event) {
    if (event.key === "Enter") {
        event.preventDefault();
        filterQuery = document.getElementById("filterResultsInput").value.trim();
        performSearchFilterAndRender();
    }
}
```

### 2. Tối ưu thuật toán xếp hạng và lọc trong `performSearchFilterAndRender()`
- Khi tìm kiếm, gộp chung từ khóa chính (`queryWords`) và từ khóa phụ (`filterWords`) để chấm điểm (`searchDatabase`).
- Sau đó, lọc nghiêm ngặt các kết quả để đảm bảo tài liệu chứa cả hai tập từ khóa.
- Việc này giúp các tài liệu khớp chính xác cụm từ chứa cả từ khóa chính và phụ (như `z234e.jpg.md`) được xếp hạng cao lên hàng đầu.

## Quy chuẩn hiển thị Alerts

> [!TIP]
> [HIỂU_YÊU_CẦU]
> Sửa lỗi không tìm thấy z234e.jpg.md khi lọc.
> Chuyển cơ chế lọc sang gõ Enter để tránh giật lag.
> Độ tự tin: 10/10.

> [!NOTE]
> [PHƯƠNG_PHÁP]
> Sử dụng combinedWords để chạy searchDatabase lấy điểm xếp hạng chuẩn.
> Thay handleFilterResultsInput bằng handleFilterResultsKeyDown kiểm tra phím Enter.

[ĐỀ_XUẤT_TỐI_ƯU]
- Gộp chung highlight từ khóa chính và phụ để UI hiển thị trực quan.

> [!WARNING]
> [CẢNH_BÁO]
> Cần chặn hành vi default của phím Enter trên ô input phụ để tránh submit form ngoài ý muốn.
> Đã xử lý: gọi `event.preventDefault()`.

[NEO_HỒI_QUY]
- Giữ nguyên cơ chế highlight text.
