---
task_name: "Readme Remaster with Liquid Glass"
date: "2026-07-06"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/DOCS/LiquidGlass/Readme.html"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/Readme.html"
---

# Thiết kế lại Readme.html của SuperSearch chuẩn Liquid Glass

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> 1. Rà soát mã nguồn SuperSearch (`app.py`) để nắm bắt đầy đủ các tính năng, giải thuật, công nghệ và cơ chế thiết kế (đã hoàn thành phân tích).
> 2. Viết lại toàn bộ `Readme.html` sử dụng phong cách Liquid Glass bóng bẩy (lqre, lqdl, lqia).
> 3. Giữ nguyên cấu trúc 3 tab thông tin chính.
> 4. Font sử dụng: `Be Vietnam Pro`.
> 5. Sử dụng logo `LogoSS256.ico` có bo viền và đổ bóng giống logo chữ "s" cũ.
> 6. Hình nền (Outer background) hỗ trợ hiệu ứng sao rơi nhiều màu (không dùng màu tối và màu nóng).

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> 1. **Kiến trúc Giao diện (CSS Liquid Glass):**
>    - Định nghĩa các biến CSS cho theme Sáng/Tối. Tông nền chủ đạo nhẹ nhàng, mát mẻ (pastel lam/tím nhạt), kính mờ clear độ mờ cao (`backdrop-filter: blur(20px)`), viền mỏng bóng bẩy.
>    - Sử dụng `@import` hoặc `<link>` để nạp font `Be Vietnam Pro` từ Google Fonts.
>    - Thêm hiệu ứng di chuột phát sáng (Mouse Glow Effect - lqia) trên các thẻ card chính.
> 2. **Hiệu ứng Sao rơi (Falling Stars Effect):**
>    - Triển khai bằng thẻ `<canvas>` chiếm toàn bộ màn hình nền phía sau.
>    - Viết script JS gọn nhẹ để render các ngôi sao lấp lánh rơi nhẹ nhàng với màu sắc dịu mát (cyan, lục nhạt, lam nhạt, tím pastel, hồng nhạt, trắng), loại bỏ hoàn toàn màu tối và các màu nóng như đỏ, cam rực.
> 3. **Logo & Thương hiệu:**
>    - Thay thế chữ "S" cũ bằng thẻ `<img>` trỏ tới file `LogoSS256.ico` (sử dụng đường dẫn tương đối phù hợp cho từng vị trí file).
>    - Áp dụng CSS: `border-radius: 12px; box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3); border: 1px solid rgba(255, 255, 255, 0.2);` để đảm bảo bo viền và đổ bóng mịn màng.
> 4. **Nội dung Chi tiết hóa (Rà soát từ app.py):**
>    - *Tab 1 (Tổng quan):* Cập nhật các tính năng chính của SS: trích xuất offline, nhận diện ảnh/PDF quét, tốc độ 0ms nhờ DB tĩnh.
>    - *Tab 2 (Kiến trúc kỹ thuật):* Mô tả chi tiết pipeline MarkItDown, cơ chế OCR fallback của `LocalOcrPdfConverter`, giải mã `.doc` chống lỗi ký tự Trung Quốc của `LocalDocConverter`, xuất bảng `.xls` của `LocalXlsConverter`, cơ chế RAM-Aware giới hạn thread động qua `GlobalMemoryStatusEx`, DB tĩnh `search_db.js`, bộ phân loại heuristics thông minh phát hiện form trống (Empty Form Template), phân loại nguồn (real content, screenshots, low-confidence OCR) và gán metadata tự động (năm, ngôn ngữ, phòng ban).
>    - *Tab 3 (Vận hành):* Các bước chạy ứng dụng, chi tiết bảng phím tắt (`Enter`, `Space`, di chuyển, `Esc`, chuột phải mở Explorer) và lưu ý lọc bỏ file rác/bản nháp.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [Readme.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/DOCS/LiquidGlass/Readme.html) (Cập nhật thành phiên bản tài liệu SuperSearch mới chuẩn Liquid Glass)
- [ ] [MODIFY] [Readme.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/Readme.html) (Cập nhật phiên bản tương tự để đồng bộ tài liệu chạy cùng phần mềm)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Giữ nguyên cấu trúc logic chuyển đổi tab thông tin bằng JavaScript hiện tại.
- Giữ nguyên cơ chế chuyển đổi chế độ giao diện sáng/tối (Dark/Light mode) dựa trên thuộc tính `data-theme`.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Cấu trúc HTML & CSS nền sao rơi
```html
<!-- Background Canvas cho hiệu ứng sao rơi -->
<canvas id="starsCanvas"></canvas>

<!-- Logo mới -->
<img src="[Relative Path]/LogoSS256.ico" class="brand-logo" alt="SuperSearch Logo">
```

### 2. Script Vẽ sao rơi nhiều màu (Canvas)
```javascript
// Khởi tạo Canvas nền sao rơi
const canvas = document.getElementById('starsCanvas');
const ctx = canvas.getContext('2d');
// Danh sách các màu dịu mát, không nóng, không tối
const colors = ['#8be9fd', '#50fa7b', '#ff79c6', '#bd93f9', '#a1c4fd', '#c2e9fb', '#ffffff'];

class Star {
    constructor() {
        this.reset();
    }
    reset() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * -canvas.height;
        this.size = Math.random() * 2 + 1;
        this.speed = Math.random() * 1.5 + 0.5;
        this.color = colors[Math.floor(Math.random() * colors.length)];
        this.opacity = Math.random() * 0.6 + 0.4;
    }
    update() {
        this.y += this.speed;
        if (this.y > canvas.height) {
            this.reset();
        }
    }
    draw() {
        ctx.save();
        ctx.globalAlpha = this.opacity;
        ctx.fillStyle = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
}
// Vòng lặp vẽ và cập nhật vị trí sao...
```

> [!WARNING]
> ### [CẢNH_BÁO]
> - Do có 2 file `Readme.html` ở 2 thư mục khác nhau, đường dẫn tương đối tới logo `LogoSS256.ico` sẽ khác nhau:
>   - Ở `DOCS/LiquidGlass/Readme.html`: `../../MDBANK/src/LogoSS256.ico`
>   - Ở `MDBANK/Readme.html`: `src/LogoSS256.ico`
> - Cần tính toán kỹ để không làm hỏng hiển thị logo trên cả 2 tệp tin.

## Đề xuất Tối ưu
- Sử dụng hiệu ứng dịch chuyển 3D nhẹ (`transform: translate3d`) khi di chuột qua các thẻ card thông tin để tạo chiều sâu mà không gây lag.
- Tự động lưu trạng thái theme đã chọn vào `localStorage`.

## Kế hoạch Kiểm thử thủ công (Manual Verification Plan)
1. Mở trực tiếp các tệp `Readme.html` trên trình duyệt Chrome hoặc Edge.
2. Kiểm tra hiệu ứng sao rơi lấp lánh trên nền background chuyển động mượt mà, xác nhận không có các màu đỏ/cam hoặc nền đen tối sẫm màu.
3. Test chuyển đổi qua lại giữa 3 tab và nút bật tắt chế độ sáng/tối xem giao diện có phản hồi chính xác hay không.
