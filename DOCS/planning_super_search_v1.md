---
task_name: "Đánh giá và tối ưu thuật toán tìm kiếm SuperSearch"
date: "2026-07-05"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Đánh giá và tối ưu thuật toán tìm kiếm SuperSearch

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> Tiến hành audit thuật toán tìm kiếm hiện tại của SuperSearch (cả phía Python Backend và JS Frontend).
> Đề xuất các cải tiến về hiệu năng, độ chính xác và độ ổn định để đạt tiêu chuẩn chạy Production.
> Thực hiện quy trình lập kế hoạch `/pl` (không sửa code trực tiếp, chờ phê duyệt).

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- **Backend**:
  - Giữ nguyên luồng xử lý đa luồng (`ThreadPoolExecutor`) và cơ chế quét file tài liệu.
  - Giữ nguyên các bộ chuyển đổi định dạng (OCR PDF, docx, xlsx, v.v.).
  - Định dạng xuất ra của file `search_db.js` phải tương thích hoàn toàn (giữ nguyên các trường thông tin cũ).
- **Frontend**:
  - Giữ nguyên giao diện UI Liquid Glass, các bộ lọc phân loại bên sidebar (Đuôi file, Năm, v.v.).
  - Giữ nguyên cơ chế hiển thị Spellcheck banner ("Did you mean?").
  - Giữ nguyên cơ chế hiển thị danh sách kết quả, Quick View và nút "Đến file gốc".

## Phân tích Audit & Đề xuất cải tiến

### 1. Vấn đề hiệu năng (Performance Bottlenecks)
- **Quét tuyến tính & Chuyển đổi dấu runtime**: Ở mỗi lượt tìm kiếm, JS frontend lặp qua toàn bộ database (có thể lên tới hàng chục MB) và gọi `removeDiacritics(doc.content)` trên nội dung từng tài liệu. Đây là nguyên nhân chính gây đơ/treo UI khi database lớn.
- **Tính toán Proximity Bonus quá nặng**: Hàm `getMinSpanProximityBonus` chạy `.split(/\s+/)` trên toàn bộ nội dung của mọi document khớp.
- **Khởi động chậm**: Lúc load trang, frontend phải split nội dung của tất cả tài liệu để tính toán `wordCount` và `averageDocLength`.
- **Thiếu Debounce Input**: Ô tìm kiếm gợi ý (`handleInput`) chạy lọc tuyến tính trên mỗi phím bấm, gây lag khi gõ nhanh.

### 2. Lỗi Logic (Logic Bugs)
- Trường `wordCount` không được backend Python tạo ra, dẫn đến `doc.wordCount` luôn bằng `undefined` ở frontend (fallback về 1). Điều này làm hỏng công thức chuẩn hóa độ dài tài liệu của BM25.

[ĐỀ_XUẤT_TỐI_ƯU]
- **Tiền xử lý phía Backend (Python)**: Tính toán sẵn `word_count`, `title_clean` (không dấu, viết thường), và `content_clean` (không dấu, viết thường) trong lúc quét tài liệu và lưu trực tiếp vào file `search_db.js`.
- **Tương thích ngược (Retrocompatibility)**: JS frontend sẽ kiểm tra nếu document đã có sẵn các trường `_clean` thì dùng ngay, nếu không mới chạy hàm chuyển đổi dấu runtime.
- **Debounce Input**: Áp dụng debounce (200ms) cho sự kiện `handleInput` của suggestions autocomplete.
- **Two-Pass Ranking (Re-ranking)**: Chỉ tính toán Proximity Bonus (`getMinSpanProximityBonus`) cho Top 100 tài liệu có điểm cơ bản cao nhất, thay vì chạy cho toàn bộ danh sách tài liệu khớp.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Việc thêm các trường `_clean` vào `search_db.js` sẽ làm tăng kích thước file cơ sở dữ liệu thêm khoảng 30-40%. Tuy nhiên, đây là sự đánh đổi cần thiết để đạt tốc độ tìm kiếm tức thời trên Client-side.
> - Cần đảm bảo thuật toán xóa dấu tiếng Việt trên Python đồng bộ 100% với hàm `removeDiacritics` trên Javascript để tránh sai lệch kết quả so khớp.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Python Backend (`app.py`)
```python
# Hàm chuẩn hóa loại bỏ dấu tiếng Việt đồng bộ với JS
def remove_diacritics(text):
    if not text: return ""
    Chuẩn hóa text dạng NFD
    Lọc bỏ các ký tự dấu tổ hợp (category Mn)
    Thay thế đ/Đ thành d/D
    Trả về text viết thường

# Trong luồng tạo db_entries của scan_and_index:
    word_count = số_lượng_từ_trong(cleaned_content)
    title_clean = remove_diacritics(original_filename)
    content_clean = remove_diacritics(cleaned_content)
    Lưu title_clean, content_clean, wordCount vào JSON db_entries
```

### 2. JS Frontend (`SuperSearch.html`)
```javascript
// Thêm debounce cho handleInput
let suggestTimeout = null;
function handleInput() {
    clearTimeout(suggestTimeout);
    suggestTimeout = setTimeout(() => {
        showSuggestions(query);
    }, 200);
}

// Tối ưu hóa tìm kiếm trong searchDatabase
function searchDatabase(searchTerm, searchWords) {
    let matched = [];
    SEARCH_DB.forEach(doc => {
        // Tận dụng trường đã tiền xử lý từ DB
        const cleanTitle = doc.title_clean || removeDiacritics(doc.title);
        const cleanContent = doc.content_clean || removeDiacritics(doc.content);
        const docLen = doc.wordCount || 1;
        
        // Tính điểm thô (BM25, matches count, metadata...)
        // KHÔNG tính proximity bonus ở đây để tránh quá tải
        ...
        matched.push({ doc, score, matchedCount });
    });

    // Sắp xếp sơ bộ theo matchedCount và score
    matched.sort();

    // Re-ranking: Chỉ tính proximity bonus cho Top 100 tài liệu hàng đầu
    if (searchWords.length >= 2) {
        const top100 = matched.slice(0, 100);
        top100.forEach(item => {
            const cleanContent = item.doc.content_clean || removeDiacritics(item.doc.content);
            item.score += getMinSpanProximityBonus(cleanContent, searchWords);
        });
        // Sắp xếp lại lần cuối
        matched.sort();
    }
    return matched;
}
```

[NEO_HỒI_QUY]
- Kiểm tra dung lượng RAM và CPU lúc chạy tìm kiếm trên cơ sở dữ liệu lớn (>15MB).
- Đảm bảo các ký tự tiếng Việt đặc biệt (ươ, ă, â, đ...) sau khi loại bỏ dấu khớp chính xác giữa Python và JS.

## Kế hoạch Xác minh (Verification Plan)

### Kiểm thử Thủ công
1. **Kiểm tra Hiệu năng & UI Freeze**:
   - Gõ từ khóa tìm kiếm nhanh liên tục trên ô tìm kiếm, kiểm tra xem giao diện gợi ý suggestions có bị đơ giật không (đã có debounce).
   - Thực hiện tìm kiếm với từ khóa phổ biến (xuất hiện nhiều trong tài liệu) trên DB lớn, đo thời gian tìm kiếm hiển thị trên UI (phải nhỏ hơn 0.05s).
2. **Kiểm tra Độ chính xác & Sắp xếp**:
   - Tìm kiếm cụm từ chính xác (ví dụ "Quy trình vận hành IT") và kiểm tra xem tài liệu chứa chính xác cụm từ đó có được đẩy lên đầu không.
   - Kiểm tra xem bộ lọc Đuôi file và Năm ở sidebar hoạt động chính xác với danh sách kết quả mới.
3. **Kiểm tra Tương thích ngược**:
   - Xóa file `search_db.js` cũ, chạy quét lại để tạo DB mới có các trường `_clean`. Kiểm tra xem tìm kiếm hoạt động bình thường.
   - Thử copy một file `search_db.js` phiên bản cũ (không có các trường `_clean`) vào thư mục `data` và kiểm tra xem frontend có tự động fallback tìm kiếm thành công không.
