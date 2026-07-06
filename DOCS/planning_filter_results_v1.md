---
task_name: "Thêm bộ lọc tìm kiếm trong kết quả"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Thêm bộ lọc tìm kiếm trong kết quả (Search in Results)

Bổ sung tính năng lọc các kết quả hiện có dựa trên từ khóa phụ nhập tại thanh tìm kiếm phụ ở sidebar.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Hàm `executeSearch`: Giữ nguyên logic tìm kiếm chính. Cần xóa từ khóa lọc phụ khi thực hiện tìm kiếm chính mới.
- Hàm `performSearchFilterAndRender`: Cần lồng thêm bộ lọc từ khóa phụ trước khi phân trang và hiển thị.
- Hàm `resetToHome`: Cần reset giá trị thanh tìm kiếm phụ về rỗng.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Thêm HTML cho bộ lọc
Tại cuối sidebar:
```html
<div class="filter-section">
    <div class="filter-title">LỌC KẾT QUẢ</div>
    <input type="text" class="filter-search-box" id="filterResultsInput" placeholder="Gõ từ khóa cần lọc" oninput="handleFilterResultsInput()">
</div>
```

### 2. Định nghĩa CSS cho ô tìm kiếm phụ
```css
.filter-search-box {
    width: 100%;
    height: 34px;
    background-color: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 0 12px;
    font-size: 12.5px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    outline: none;
    transition: var(--transition-snappy);
}
.filter-search-box:hover,
.filter-search-box:focus {
    background-color: var(--glass-hover-bg);
    border-color: var(--accent-blue);
}
```

### 3. Logic JavaScript lọc phụ
```javascript
// Biến lưu từ khóa lọc phụ toàn cục
let filterQuery = "";

// Hàm xử lý đầu vào từ thanh tìm kiếm phụ
function handleFilterResultsInput() {
    filterQuery = document.getElementById("filterResultsInput").value.trim();
    performSearchFilterAndRender();
}
```

Tích hợp lọc phụ vào `performSearchFilterAndRender()`:
- Nếu `filterQuery` khác rỗng:
  - Tách từ khóa bằng khoảng trắng.
  - Lọc danh sách `results` sao cho tiêu đề hoặc nội dung tài liệu chứa toàn bộ các từ khóa lọc.
  - Thêm từ khóa lọc vào mảng highlight để bôi đậm trên UI.

## Quy chuẩn hiển thị Alerts

> [!TIP]
> [HIỂU_YÊU_CẦU]
> Thêm ô tìm kiếm phụ ở chân sidebar.
> Lọc trực tiếp trên tập kết quả hiện thời.
> Độ tự tin: 10/10.

> [!NOTE]
> [PHƯƠNG_PHÁP]
> Thêm biến toàn cục filterQuery.
> Lọc mảng results trước khi gán cho filteredResults.
> Reset input khi tìm kiếm chính hoặc về trang chủ.

[ĐỀ_XUẤT_TỐI_ƯU]
- Tự động highlight từ khóa lọc phụ để tăng trải nghiệm người dùng.

> [!WARNING]
> [CẢNH_BÁO]
> Lọc phụ trên tập kết quả lớn có thể gây chậm nếu thực hiện thủ công phức tạp.
> Giải pháp: Chỉ lọc trên mảng results đã tìm kiếm được, hiệu năng tối ưu.

[NEO_HỒI_QUY]
- Giữ nguyên các dropdown filter hiện có.
