---
task_name: "Audit và sửa lỗi tìm kiếm rỗng cùng các lỗi ngầm SuperSearch"
date: "2026-07-03"
version: "v2"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Khắc phục Lỗi tìm kiếm rỗng và Rà soát lỗi ngầm SuperSearch

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> Rà soát kỹ lưỡng lý do tại sao gõ bất kỳ từ khóa nào cũng không trả về kết quả, phát hiện các lỗi ngầm và lập kế hoạch sửa đổi hoàn chỉnh.
> **Các phát hiện cốt lõi:**
> 1. **Lỗi sai đường dẫn tương đối (Lỗi chí mạng)**: File `SuperSearch.html` và `search_db.js` nằm cùng thư mục `MDBANK/data/`. Tuy nhiên, trong HTML lại load script từ `"data/search_db.js"`. Điều này khiến WebView cố gắng tìm kiếm ở `MDBANK/data/data/search_db.js` dẫn đến lỗi 404 Not Found, làm biến `SEARCH_DB` bị undefined và tê liệt tìm kiếm.
> 2. **Lỗi crash RegExp Lookbehind**: Ở một số phiên bản WebView cũ trên Windows (không hỗ trợ ES2018 lookbehind `(?<!...)`), hàm `highlightText` và `highlightElementTextNodes` bị lỗi SyntaxError khi khởi tạo RegExp, gây crash JS và treo giao diện kết quả.
> 3. **Lỗi mã hóa dữ liệu**: Thẻ script nạp database thiếu thuộc tính `charset="utf-8"`, dẫn đến việc các ký tự Unicode tiếng Việt có dấu bị giải mã sai thành ký tự rác (Mojibake) hoặc lỗi cú pháp JS trên một số máy cấu hình ANSI mặc định.
> 4. **Lỗi query string trên file://**: Sử dụng query string `?t=` khi reload script trên giao thức `file://` bị lỗi phân giải đường dẫn trên một số phiên bản Windows.
>
> Điểm tin cậy: 10/10.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên thuật toán xếp hạng tìm kiếm BM25 cục bộ.
- Giữ nguyên cấu trúc dữ liệu `SEARCH_DB` được tạo ra từ backend Python.
- Đảm bảo giữ nguyên các cờ trạng thái tìm kiếm (`autocorrectEnabled`, bộ lọc, v.v.).

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> Triển khai các bước điều chỉnh đường dẫn và RegExp tương thích ngược:
> 1. Sửa đường dẫn nạp database từ `"data/search_db.js"` thành `"search_db.js"` tại thẻ script ban đầu và hàm reload.
> 2. Thêm thuộc tính `charset="utf-8"` vào thẻ script nạp database.
> 3. Loại bỏ RegExp Lookbehind trong highlight, thay thế bằng capture group ranh giới từ phía trước kết hợp callback kiểm tra điều kiện.

[ĐỀ_XUẤT_TỐI_ƯU]
- Thay đổi đường dẫn tương đối và thêm charset là giải pháp tối ưu nhất, giải quyết triệt để lỗi 404 nạp file JS.
- Loại bỏ hoàn toàn lookbehind RegExp giúp ứng dụng chạy ổn định trên mọi phiên bản WebView Windows mà không phụ thuộc vào phiên bản Edge/WebView2.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Do `SuperSearch.html` chạy local qua giao thức `file://`, việc chỉ định đường dẫn tương đối phải cực kỳ chính xác. Không được sử dụng các đường dẫn tuyệt đối hoặc query string làm lỗi hệ thống file Windows.

[NEO_HỒI_QUY]
- Giữ nguyên cấu trúc file `search_db.js` được tạo từ Python backend để đảm bảo tính đồng bộ.

### Mã giả / Giải thuật đề xuất

#### 1. Sửa đường dẫn nạp script ban đầu
```html
<script src="search_db.js" charset="utf-8"></script>
```

#### 2. Sửa hàm reloadSearchDatabase
```javascript
function reloadSearchDatabase() {
    // Tìm và xóa thẻ script cũ với đường dẫn tương đối mới
    const oldScript = document.querySelector('script[src^="search_db.js"]');
    // ...
    const script = document.createElement('script');
    script.src = "search_db.js";
    script.charset = "utf-8";
    // ...
}
```

#### 3. Thay thế Lookbehind bằng callback tương thích ngược
```javascript
// Thay thế RegExp: (?<!vtLetters)(accentPattern)(?!vtLetters)
// Thành: (vtLetters?)(accentPattern)(?!vtLetters)
const flexRegex = new RegExp('(' + vtLetters + '?)(' + accentPattern + ')(?!' + vtLetters + ')', 'gi');
highlighted = highlighted.replace(flexRegex, (match, p1, p2) => {
    // Nếu có ký tự trước (p1) -> nằm trong từ khác -> không highlight
    return p1 ? match : startTag + p2 + endTag;
});
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. Mở ứng dụng SuperSearch.exe (hoặc nạp SuperSearch.html trong WebView).
2. Kiểm tra xem badge hiển thị đúng số lượng tài liệu thực tế (ví dụ: `688 tài liệu`), chứng tỏ `SEARCH_DB` đã nạp thành công.
3. Gõ từ khóa tìm kiếm tiếng Việt và kiểm tra kết quả hiển thị chính xác cùng highlight đúng ranh giới từ.
