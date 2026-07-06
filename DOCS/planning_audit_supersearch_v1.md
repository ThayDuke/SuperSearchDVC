---
task_name: "Audit và tối ưu hóa ứng dụng SuperSearch"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Audit và Tối ưu hóa Ứng dụng SuperSearch

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> Thực hiện đánh giá (audit) toàn diện ứng dụng SuperSearch bao gồm cả Backend (Python `app.py`) và Frontend (HTML/JS/CSS `SuperSearch.html`). Mục tiêu là phát hiện lỗi lập trình, lỗ hổng bảo mật, thuật toán kém tối ưu, nợ kỹ thuật và đề xuất giải pháp tái cấu trúc an toàn, đạt chuẩn production cao nhất.

---

## 1. Kết quả Audit Chi tiết (Các điểm yếu & Lỗi lập trình)

### A. Kiến trúc & Phân bổ Codebase (Nợ kỹ thuật lớn)
- **Vấn đề Monolithic Frontend:** File [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SuperSearch.html) chứa hơn 3500 dòng code trộn lẫn HTML, CSS, SVG và logic JavaScript (từ dựng giao diện, hạt animation, spellcheck đến thuật toán tìm kiếm xếp hạng). Rất khó bảo trì, kiểm thử và nâng cấp.
- **Import thư viện động lãng phí:** Trong [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py), các thư viện nặng (`pandas`, `pytesseract`, `pdfplumber`, `PIL`, `markitdown`) được import động bên trong hàm `scan_and_index`. Điều này làm chậm trễ đáng kể thời điểm bắt đầu quét mỗi khi người dùng nhấn nút do Python phải nạp lại thư viện.

### B. Hiệu năng & Thuật toán (Performance Bottlenecks)
- **Tìm kiếm Client-Side quá tải:** Toàn bộ dữ liệu `SEARCH_DB` được nạp vào bộ nhớ trình duyệt và việc tìm kiếm được thực hiện trực tiếp trên Main Thread của trình duyệt bằng JS. Khi số lượng tài liệu tăng lên hàng nghìn, việc lặp qua toàn bộ DB và chạy nhiều biểu thức chính quy (Regex) phức tạp cho mỗi kết quả sẽ làm block hoàn toàn UI, gây đơ giao diện.
- **Khóa OCR (OCR Lock) làm giảm hiệu suất đa luồng:** Việc sử dụng một `ocr_lock = threading.Lock()` dùng chung cho tất cả các luồng trong `ThreadPoolExecutor` khiến các tác vụ OCR bị xếp hàng tuần tự. Điều này vô hiệu hóa lợi ích của đa luồng khi xử lý nhiều tài liệu PDF dạng quét (scanned PDF) hoặc tệp hình ảnh.
- **Cơ chế dừng/tạm dừng quét phản hồi chậm:** Trong `run_single_task`, luồng chỉ kiểm tra cờ dừng/tạm dừng ở đầu task hoặc trước khi ghi file. Nếu một file PDF lớn đang chạy OCR (mất vài phút), luồng đó không thể bị ngắt ngay lập tức, khiến nút "Hủy quét" (Abort) hoặc "Tạm dừng" (Pause) phản hồi rất chậm.

### C. An toàn dữ liệu & Lỗ hổng Bảo mật (Security & Data Integrity)
- **Nguy cơ xóa nhầm dữ liệu quét cũ:** Khi quá trình quét bị hủy nửa chừng (`self._scan_aborted = True`), tập hợp `expected_markdown_files` mới chỉ được thu thập một phần. Đoạn code dọn dẹp file mồ côi (dòng 988-997) sẽ quét và xóa sạch tất cả các file `.md` đã được index thành công ở các thư mục khác từ trước đó, gây mất mát dữ liệu nghiêm trọng.
- **Lỗ hổng Cross-Site Scripting (XSS):** Hàm `highlightText` và `getSmartSnippet` chèn thẻ `<mark>` vào văn bản rồi trả về HTML string, sau đó được gán trực tiếp vào DOM bằng `innerHTML` trong `renderResultsList`. Nếu nội dung tài liệu hoặc tên file chứa mã độc JS (ví dụ: `<img src=x onerror=... >`), mã độc sẽ được thực thi ngay khi người dùng thấy kết quả tìm kiếm hoặc mở Quick View.
- **Thuật toán sửa tiếng Trung (Mojibake) phỏng đoán thiếu an toàn:** Hàm `LocalDocConverter` xử lý lỗi mã hóa file `.doc` bằng cách lọc ký tự bằng biểu thức chính quy và giải mã nhị phân thô. Việc này rất dễ làm hỏng nội dung nguyên bản của các tài liệu tiếng Anh/Việt chứa ký tự đặc biệt hợp lệ.

---

## 2. Giải pháp Đề xuất & Phương pháp Xử lý

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> Triển khai các biện pháp tối ưu hóa và sửa lỗi theo lộ trình an toàn, không làm gián đoạn các tính năng hiện tại của ứng dụng:
> 1. **Bảo mật:** Khử trùng độc (Sanitize) toàn bộ dữ liệu trước khi chèn vào `innerHTML` để triệt tiêu lỗ hổng XSS.
> 2. **Hiệu năng:** Tách biệt luồng tìm kiếm nặng sang Web Worker (hoặc chuyển một phần về Python SQLite FTS5) để giải phóng Main Thread. Cải tiến cơ chế ngắt luồng OCR.
> 3. **Tái cấu trúc:** Tách file HTML monolithic thành các module nhỏ (`app.js`, `styles.css`) và chuyển các import nặng trong Python lên đầu module hoặc sử dụng cơ chế Lazy Loading thông minh chỉ nạp một lần.
> 4. **An toàn dữ liệu:** Sửa logic xóa file mồ côi: Chỉ xóa các file mồ côi khi và chỉ khi quá trình quét hoàn thành 100% không bị hủy giữa chừng.

[ĐỀ_XUẤT_TỐI_ƯU]
- Sử dụng hàm escape HTML tối giản để ngăn chặn XSS mà vẫn giữ được thẻ `<mark>`.
- Tách file `SuperSearch.html` thành các file chức năng riêng biệt để chuẩn hóa dự án cấp độ production.
- Sửa logic dọn dẹp file `.md` mồ côi trong `app.py`.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Việc thay đổi cấu trúc file có thể ảnh hưởng đến đường dẫn tương đối khi build file EXE bằng PyInstaller. Cần cập nhật file `.spec` tương ứng.
> - Việc sửa đổi cơ chế khôi phục file gốc từ thư mục `ORIGINAL` cần được thực hiện cực kỳ cẩn thận để tránh mất dữ liệu gốc của người dùng.

---

## 3. Kiến trúc Giải thuật & Mã giả (Pseudocode)

### A. Hàm Khử trùng độc HTML ngăn chặn XSS (Frontend)
```javascript
function safeHighlight(text, searchWords) {
    let escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    // Tiến hành highlight trên văn bản đã được escape an toàn
    // Chỉ sinh ra thẻ <mark class="highlight-mark">
    return highlightedContent;
}
```

### B. Logic dọn dẹp file mồ côi an toàn (Backend - app.py)
```python
# Chỉ dọn dẹp file mồ côi khi quét thành công hoàn toàn
if not self._scan_aborted:
    for root, dirs, files in os.walk(markdown_root):
        for file in files:
            md_path = os.path.normpath(os.path.join(root, file))
            if md_path not in expected_markdown_files:
                try:
                    os.remove(md_path)
                except Exception as e:
                    print(e)
```

---

## 4. Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (Manual Verification)
1. **Kiểm tra XSS:** Tạo một file `.md` chứa nội dung `<script>alert('xss')</script>`. Thực hiện tìm kiếm từ khóa đó và xác nhận không có hộp thoại alert nào bật lên.
2. **Kiểm tra hủy quét (Abort Scan):** Bắt đầu quét một thư mục lớn, nhấn nút "Hủy quét". Xác nhận quá trình dừng lại ngay lập tức và các file markdown đã được quét từ trước đó không bị xóa mất.
3. **Kiểm tra Hiệu năng Tìm kiếm:** Thực hiện tìm kiếm với một từ khóa phổ biến xuất hiện ở hầu hết các tài liệu và đo thời gian phản hồi của UI (không có hiện tượng đơ chuột/giao diện).

---
[PROJECT_CHECKPOINT] Trạng thái phân tích hệ thống được thiết lập. Sẵn sàng nhận lệnh triển khai.
