---
task_name: "Tối ưu hóa Searchbar và nút chuyển đổi Theme"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Tối ưu hóa Searchbar và nút chuyển đổi Theme

Tái cấu trúc giao diện phần đầu trang tìm kiếm: đưa số lượng tài liệu vào bên trong searchbar như thông tin tĩnh, căn giữa nút "Quét và index", thu gọn nút chuyển đổi Theme thành hình tròn chứa icon đơn sắc Moon/Sun nằm bên phải searchbar.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- **Hàm cập nhật thống kê (`buildDashboardStats`):** Giữ nguyên logic cập nhật `textContent` cho phần tử `#docCountBtn` để tránh lỗi logic liên quan đến đếm file.
- **Hàm `toggleTheme`:** Giữ nguyên logic chuyển trạng thái giao diện và ghi nhớ vào `localStorage`.

## Thiết kế Chi tiết & Mã giả (Architecture & Pseudocode)

> [!TIP]
> **[HIỂU_YÊU_CẦU]**
> - Nút hiển thị số tài liệu (`#docCountBtn`) được chuyển đổi từ một nút tương tác ở hàng dưới thành một tag tĩnh đặt ở góc phải bên trong Search Box. Nó sẽ ẩn đi khi người dùng nhập từ khóa tìm kiếm (hoạt động như placeholder).
> - Nút Quét và Index (`#scanBtn`) sẽ là nút duy nhất còn lại trong hàng nút, tự động căn giữa do layout flexbox.
> - Nút Theme (`#themeToggleBtn`) bỏ chữ "Tối"/"Sáng", thay đổi kích thước thành hình tròn (40px x 40px), chứa icon SVG đơn sắc (mặt trăng/mặt trời) và nằm bên phải searchbar.

> [!NOTE]
> **[PHƯƠNG_PHÁP]**
>
> **1. Thay đổi cấu trúc HTML:**
> - Di chuyển `#docCountBtn` (đổi thẻ từ `button` sang `span`) vào trong `.search-box-wrapper`.
> - Loại bỏ phần tử `#docCountBtn` cũ khỏi `#landingButtonsRow`.
> - Cập nhật `#themeToggleBtn` để chỉ chứa SVG thay vì Emoji và thẻ `span`.
>
> **2. Cập nhật CSS:**
> - Thêm lớp `.search-doc-count-badge` cho `#docCountBtn` mới với định vị tuyệt đối bên phải:
>   ```css
>   .search-doc-count-badge {
>       position: absolute;
>       right: 16px;
>       top: 50%;
>       transform: translateY(-50%);
>       pointer-events: none;
>       font-size: 13px;
>       color: var(--text-secondary);
>       opacity: 0.6;
>       z-index: 2;
>       transition: opacity 0.2s ease, visibility 0.2s ease;
>       user-select: none;
>       white-space: nowrap;
>   }
>   ```
> - Sử dụng CSS selector để tự động ẩn badge này khi input có nội dung:
>   ```css
>   .search-box:not(:placeholder-shown) ~ .search-doc-count-badge {
>       opacity: 0;
>       visibility: hidden;
>   }
>   ```
> - Thay đổi `.theme-toggle-btn` thành dạng vòng tròn:
>   ```css
>   .theme-toggle-btn {
>       background: var(--glass-bg);
>       border: 1px solid var(--glass-border);
>       color: var(--text-primary);
>       height: 40px;
>       width: 40px;
>       padding: 0;
>       border-radius: 50%;
>       cursor: pointer;
>       transition: var(--transition-snappy);
>       display: flex;
>       align-items: center;
>       justify-content: center;
>       box-shadow: var(--card-shadow);
>       backdrop-filter: blur(10px);
>       -webkit-backdrop-filter: blur(10px);
>       flex-shrink: 0;
>   }
>   ```
>
> **3. Cập nhật JS:**
> - Sửa đổi hàm `setTheme(theme)` để chèn SVG đơn sắc thay thế cho Emoji + Text cũ:
>   - Theme dark: Chèn SVG Sun (đơn sắc, dùng `stroke="currentColor"`).
>   - Theme light: Chèn SVG Moon (đơn sắc, dùng `stroke="currentColor"`).

> [!WARNING]
> **[CẢNH_BÁO]**
> - Việc thay đổi thẻ của `#docCountBtn` từ `button` sang `span` không làm ảnh hưởng đến JS vì JS chỉ truy cập qua `document.getElementById("docCountBtn")` và ghi đè `.textContent`. Tuy nhiên, cần đảm bảo không có mã CSS cũ nào ghi đè làm hỏng thuộc tính hiển thị tuyệt đối của badge trong searchbar.
