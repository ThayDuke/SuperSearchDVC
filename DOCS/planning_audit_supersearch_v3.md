---
task_name: "Tối ưu thuật toán tìm kiếm và sửa lỗi highlight đè tag"
date: "2026-07-03"
version: "v3"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Tối ưu Thuật toán Tìm kiếm và Sửa lỗi Highlight Đè Tag

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> Sửa lỗi highlight bị vỡ cấu trúc và tràn ngập ký tự ngắn (như chữ "a") khi tìm kiếm các cụm từ có chứa từ dừng hoặc từ quá ngắn.
> **Các nguyên nhân chính:**
> 1. **Đè tag highlight (Tag Collision)**: Tag trung gian dạng chuỗi chữ `"___HG_START___"` chứa ký tự `"A"`. Khi duyệt qua từ khóa `"a"`, RegExp sẽ khớp và thay thế chữ `"A"` trong chính tag trung gian đã chèn trước đó, làm vỡ cấu trúc HTML kết quả.
> 2. **Chưa lọc từ dừng và từ quá ngắn (Stopwords/Shortwords)**: Các từ cực ngắn (1 ký tự) hoặc các từ dừng phổ biến (`with`, `a`, `of`, `của`, `và`...) bị đối xử như từ khóa chính, làm loãng highlight và sai lệch điểm số xếp hạng.
>
> Điểm tin cậy: 10/10.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên các hàm bổ trợ UI khác.
- Đảm bảo logic xếp hạng BM25 và độ tương thích ngược không dùng lookbehind RegExp hoạt động ổn định.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> Thực hiện tái cấu trúc logic tách từ khóa và thay thế tag highlight:
> 1. **Dùng tag trung gian an toàn**: Đổi `startTag` thành ký tự đặc biệt `\uE000` và `endTag` thành `\uE001` (vùng Private Use Area không trùng với bất kỳ chữ cái nào).
> 2. **Lọc từ dừng và từ quá ngắn**: Thiết lập danh sách `STOP_WORDS` và chỉ thực hiện tìm kiếm/highlight các từ có độ dài `> 1` và không nằm trong danh sách từ dừng khi truy vấn có nhiều từ.
> 3. **Tối ưu hóa chấm điểm BM25**: Loại bỏ các từ dừng khỏi công thức cộng điểm từ khóa để nâng cao độ chính xác.

[ĐỀ_XUẤT_TỐI_ƯU]
- Sử dụng ký tự Unicode đặc biệt `\uE000` và `\uE001` là giải pháp triệt để nhất loại bỏ hoàn toàn khả năng đè tag.
- Việc lọc từ dừng vừa giúp tăng tốc độ tìm kiếm client-side, vừa cải thiện đáng kể giao diện hiển thị kết quả (chỉ highlight từ quan trọng).

> [!WARNING]
> ### [CẢNH_BÁO]
> - Cần giữ cơ chế fallback nếu người dùng chỉ gõ duy nhất một từ khóa là từ dừng hoặc từ 1 ký tự (để họ vẫn tìm được chính xác ký tự đó nếu muốn).

[NEO_HỒI_QUY]
- Giữ nguyên cấu trúc dữ liệu `SEARCH_DB`.

### Mã giả / Giải thuật đề xuất

#### 1. Đổi tag trung gian an toàn trong SuperSearch.html
```javascript
const startTag = "\uE000";
const endTag = "\uE001";
```

#### 2. Định nghĩa danh sách Stopwords và lọc từ khóa
```javascript
const STOP_WORDS = new Set(["with", "of", "the", "and", "in", "on", "at", "to", "for", "a", "an", "va", "cua", "nhung", "cac", "cho", "trong", "tren", "tai"]);

function filterSearchWords(queryWords) {
    if (queryWords.length <= 1) return queryWords;
    const filtered = queryWords.filter(w => w.length > 1 && !STOP_WORDS.has(w));
    return filtered.length > 0 ? filtered : queryWords;
}
```

#### 3. Cập nhật hàm performSearchFilterAndRender
```javascript
function performSearchFilterAndRender() {
    // ...
    const queryWords = cleanQuery.split(/\s+/).filter(w => w.length > 0);
    // Lọc từ khóa
    const searchWords = filterSearchWords(queryWords);
    // ...
}
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. Mở SuperSearch.exe.
2. Tìm kiếm cụm từ `"monitoring with a tool"`.
3. Xác nhận:
   - Các chữ `"a"` trong các từ khác (như `smart`, `features`) không bị bôi đậm.
   - Thẻ tag highlight không bị hiển thị chuỗi rác `___HG_ST...` trên màn hình.
   - Kết quả tìm kiếm xếp hạng chính xác tài liệu chứa `"monitoring"` và `"tool"` lên đầu.
