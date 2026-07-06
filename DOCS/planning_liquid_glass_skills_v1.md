---
task_name: "Liquid Glass Web and Windows Skills Creation"
date: "2026-07-01"
version: "v1"
status: "Draft"
target_files:
  - "C:/Users/DUKE NGUYEN/.gemini/config/skills/liquid-glass-web-win/SKILL.md"
  - "C:/Users/DUKE NGUYEN/.gemini/config/skills/liquid-glass-web-win/references/liquid-glass-web.md"
---

# Kế hoạch phát triển bộ Skill Liquid Glass cho Web/Windows

Kế hoạch này đề xuất cấu trúc và nội dung cho bộ kỹ năng mới giúp phát triển giao diện Apple Liquid Glass trên nền tảng Web (HTML/JS/CSS) và Windows local app (Electron/Tauri).

## Phạm vi Thay đổi (Impact Scope)
- [ ] [NEW] `C:/Users/DUKE NGUYEN/.gemini/config/skills/liquid-glass-web-win/SKILL.md`
- [ ] [NEW] `C:/Users/DUKE NGUYEN/.gemini/config/skills/liquid-glass-web-win/references/liquid-glass-web.md`

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Bộ skill phải được kích hoạt tự động khi người dùng yêu cầu thiết kế UI Liquid Glass trên Web/Windows.
- Đảm bảo tính nhất quán của các lệnh: `lqcr`, `lqre`, `lqdl`.
- Sử dụng các chuẩn CSS hiện đại tương thích tốt trên Edge/Chrome/Tauri (Windows).

## Phân tích & Kiến trúc

> [!TIP]
> [HIỂU_YÊU_CẦU]
> - Người dùng cần bộ skill dùng chung cho mọi dự án Web/Windows.
> - Bắt buộc có 3 lệnh chính: `lqcr`, `lqre`, `lqdl`.
> - Đề xuất thêm các skill bổ trợ quan trọng.
> - Điểm tin cậy: 10/10.

> [!NOTE]
> [PHƯƠNG_PHÁP]
> - Tạo cấu trúc thư mục skill tại Global Customizations Root (`.gemini/config/skills`).
> - File `SKILL.md` định nghĩa trigger, hướng dẫn thực thi cho từng lệnh (`lqcr`, `lqre`, `lqdl`).
> - File `references/liquid-glass-web.md` chứa mã nguồn CSS/JS mẫu chuẩn hóa.
> - Đề xuất thêm 2 lệnh phụ: `lqpf` (Performance) và `lqia` (Interactive Animations).

[ĐỀ_XUẤT_TỐI_ƯU]
- Xây dựng hệ thống CSS variables tập trung để xử lý đồng bộ Light/Dark mode.
- Cung cấp mã giả/khung CSS chuẩn cho từng cấu trúc kính (Card, Button, Input).
- Tận dụng `backdrop-filter` và `mask-image` để tạo viền sáng động.

> [!WARNING]
> [CẢNH_BÁO]
> - Nhiều lớp kính chồng chéo gây tụt FPS trên Windows cấu hình yếu.
> - `backdrop-filter` có thể bị lỗi hiển thị nếu phần tử cha có thuộc tính `transform`.

[NEO_HỒI_QUY]
- Không thay đổi các quy tắc toàn cục của hệ thống Agent.
- Kế thừa cách tổ chức file của repository mẫu để người dùng dễ kiểm soát.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Cấu trúc SKILL.md mẫu
```markdown
# Liquid Glass Web and Windows Development Skill

## Triggers
- "lqcr", "lqre", "lqdl"
- "tạo giao diện liquid glass cho web"
- "remaster giao diện sang glassmorphism"

## Hướng dẫn thực thi

### Lệnh lqcr: Liquid Create
- Bước 1: Khởi tạo layout CSS biến thể kính.
- Bước 2: Thiết lập CSS variables cho Light/Dark mode.
- Bước 3: Áp dụng lớp phủ glass cho component.

### Lệnh lqre: Liquid Remaster
- Bước 1: Phân tích cấu trúc DOM cũ.
- Bước 2: Thay thế background, border, shadow cũ bằng CSS Glass.
- Bước 3: Gắn thẻ container cho các vùng kính.

### Lệnh lqdl: Liquid Dark-Light
- Bước 1: Định nghĩa bảng màu kính cho cả 2 mode.
- Bước 2: Đồng bộ hóa sự kiện chuyển đổi theme (class body).

### Lệnh đề xuất bổ sung:
- **lqpf (Liquid Performance)**: Giảm số lượng lớp blur, sử dụng hardware acceleration.
- **lqia (Liquid Interaction)**: Hiệu ứng ánh sáng đuổi theo con trỏ chuột (Mouse glow).
```

### 2. Cấu trúc CSS Template trong references
```css
/* Thiết lập CSS Variables dùng chung */
:root {
  /* Light Mode Glass */
  --lg-bg: rgba(255, 255, 255, 0.4);
  --lg-border: rgba(255, 255, 255, 0.3);
  --lg-blur: 12px;
  --lg-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
}

[data-theme="dark"] {
  /* Dark Mode Glass */
  --lg-bg: rgba(15, 23, 42, 0.45);
  --lg-border: rgba(255, 255, 255, 0.08);
  --lg-blur: 16px;
  --lg-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
}

/* Base Glass Class */
.liquid-glass {
  background: var(--lg-bg);
  backdrop-filter: blur(var(--lg-blur));
  -webkit-backdrop-filter: blur(var(--lg-blur));
  border: 1px solid var(--lg-border);
  box-shadow: var(--lg-shadow);
}
```

---

## Kế hoạch Xác minh (Verification Plan)
- Kiểm tra cú pháp Markdown của file `SKILL.md` và `liquid-glass-web.md`.
- Đảm bảo các đường dẫn file tuyệt đối chính xác trên môi trường Windows.
