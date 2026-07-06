---
task_name: "Cấu hình vạch highlight trên scrollbar chi tiết file"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Cấu hình Vạch Định vị Highlight trên Scrollbar Modal Chi Tiết File

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> Nâng cao trải nghiệm đọc file chi tiết bằng cách thêm vạch định vị highlight (minimap markers) trên scrollbar của modal và tự động cuộn đến highlight đầu tiên khi mở.
> **Các tính năng cần thêm:**
> 1. Custom thanh định vị dọc (#scrollbarMarkerTrack) đè lên scrollbar của modal.
> 2. Tính toán tỷ lệ vị trí của các thẻ `<mark.highlight-mark>` để vẽ các vạch vàng tương ứng.
> 3. Click vào vạch sẽ tự động cuộn mượt (smooth scroll) đến vị trí highlight đó.
> 4. Tự động cuộn đến vị trí highlight đầu tiên ngay khi mở modal.
>
> Điểm tin cậy: 10/10.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên cơ chế highlight text bằng thẻ `mark.highlight-mark`.
- Giữ nguyên nội dung và định dạng hiển thị Markdown của file.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> **Bước 1: Cập nhật CSS**
> - Thêm CSS cho `.scrollbar-marker` (vạch định vị màu vàng cam, hover scale và thay đổi con trỏ).
> - Thêm CSS đảm bảo wrapper của modal-body có `position: relative` để định vị track.
>
> **Bước 2: Cập nhật cấu trúc HTML**
> - Bọc `modal-body` và thẻ `#scrollbarMarkerTrack` mới vào trong một wrapper tương đối.
>
> **Bước 3: Cập nhật Javascript trong `openQuickView`**
> - Sau khi nạp HTML vào modal, dùng `setTimeout` để chờ render và lấy `scrollHeight`/`clientHeight`.
> - Tính tỷ lệ vị trí từng thẻ `mark` và append các marker tương ứng vào `#scrollbarMarkerTrack`.
> - Gắn sự kiện `onclick` cho mỗi marker cuộn mượt modal body đến vị trí thẻ `mark` đó.
> - Tự động gọi `scrollTo` đến vị trí thẻ `mark` đầu tiên.

[ĐỀ_XUẤT_TỐI_ƯU]
- Định vị marker bằng đơn vị `px` động tính theo `(mark.offsetTop / scrollHeight) * clientHeight` giúp vị trí các vạch khớp hoàn hảo tuyệt đối với tay cuộn (scrollbar thumb) bất kể chiều cao modal lớn hay nhỏ.
- Sử dụng `pointer-events: none` trên track container và `pointer-events: auto` trên các vạch giúp người dùng vừa click được vạch vừa kéo thả được scrollbar mặc định bên dưới.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Do modal body có padding (`padding: 1.5rem`), cần tính toán vị trí offset chính xác hoặc cuộn chừa lề (`containerHeight / 3`) để highlight không bị che khuất bởi header của modal.

[NEO_HỒI_QUY]
- Giữ nguyên tính năng đóng modal bằng phím Escape và click ngoài vùng phủ.

### Mã giả / Giải thuật đề xuất

#### 1. HTML Wrapper mới trong modal
```html
<div style="position: relative; display: flex; width: 100%;">
    <div class="modal-body" id="modalBody"></div>
    <div id="scrollbarMarkerTrack"></div>
</div>
```

#### 2. CSS bổ sung cho vạch định vị
```css
.scrollbar-marker {
    position: absolute;
    right: 2px;
    width: 10px;
    height: 3px;
    background-color: #f59e0b;
    box-shadow: 0 0 4px rgba(245, 158, 11, 0.8);
    cursor: pointer;
    pointer-events: auto;
    z-index: 11;
    transition: transform 0.1s ease;
}
.scrollbar-marker:hover {
    transform: scaleX(1.3);
    background-color: #d97706;
}
```

#### 3. Cập nhật logic Javascript trong openQuickView
```javascript
// ... sau khi gán modalBody.innerHTML
const markerTrack = document.getElementById("scrollbarMarkerTrack");
if (markerTrack) {
    markerTrack.innerHTML = "";
    setTimeout(() => {
        const marks = modalBody.querySelectorAll("mark.highlight-mark");
        const scrollHeight = modalBody.scrollHeight;
        const containerHeight = modalBody.clientHeight;
        
        if (scrollHeight > 0 && marks.length > 0) {
            marks.forEach((mark, idx) => {
                const ratio = mark.offsetTop / scrollHeight;
                const marker = document.createElement("div");
                marker.className = "scrollbar-marker";
                marker.style.top = (ratio * containerHeight) + "px";
                marker.onclick = (e) => {
                    e.stopPropagation();
                    modalBody.scrollTo({
                        top: mark.offsetTop - (containerHeight / 3),
                        behavior: "smooth"
                    });
                };
                markerTrack.appendChild(marker);
            });
            
            // Cuộn đến vạch đầu tiên
            modalBody.scrollTo({
                top: marks[0].offsetTop - (containerHeight / 3),
                behavior: "smooth"
            });
        }
    }, 150);
}
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. Mở SuperSearch.exe.
2. Tìm kiếm từ khóa có tần suất xuất hiện cao trong các file dài (ví dụ: `the` hoặc `judo`).
3. Click vào một card kết quả dài để mở modal chi tiết.
4. Xác nhận:
   - Modal tự động cuộn đến vị trí highlight đầu tiên.
   - Xuất hiện các vạch màu vàng cam ở cạnh phải sát scrollbar.
   - Click vào một vạch bất kỳ và xác nhận modal cuộn mượt đến đúng vị trí highlight đó.
