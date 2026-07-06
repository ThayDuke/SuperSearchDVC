---
task_name: "Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 2"
date: "2026-07-05"
version: "v5"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 2

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Tiến hành audit thuật toán tìm kiếm SuperSearch ở mức độ chuyên gia.
> - Khắc phục các lỗi về độ chính xác (highlight sai lệch, mất stopwords Việt quan trọng).
> - Tối ưu hiệu năng (thuật toán Proximity O(N) thay vì O(K*N), lọc spelling candidates thông minh tránh bỏ sót từ).
> - Sửa lỗi lạm phát độ dài BM25 do expand compound token làm sai lệch điểm xếp hạng tài liệu.
> - Đảm bảo hệ thống hoạt động ổn định và sẵn sàng đạt chuẩn Production.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên cấu trúc dữ liệu chính trong `search_db.js`.
- Giữ nguyên thiết kế và các trạng thái UI Liquid Glass.
- Không thay đổi các phương thức OCR trong Python backend.

---

## Kết quả Đánh giá Thuật toán & Đề xuất (Audit Findings)

### 1. Thuật toán Proximity Bonus (Độ phức tạp O(K * N))
- **Vấn đề:** Hàm `getMinSpanProximityBonus` lặp qua toàn bộ mảng từ của tài liệu nhiều lần bằng `.forEach` cho từng từ trong câu truy vấn (K lần, với N là độ dài văn bản). Với file lớn (N > 5000) và câu truy vấn dài, tốc độ xử lý sẽ bị suy giảm nghiêm trọng.
- **Giải pháp:** Tối ưu xuống O(N) bằng cách lặp qua tài liệu đúng một lần để gom nhóm các vị trí của toàn bộ từ khóa thông qua Map tra cứu nhanh.

### 2. Bug logic trong Spelling Correction (Sửa lỗi chính tả)
- **Vấn đề:** Việc `slice(0, 1200)` danh sách ứng viên thô TRƯỚC KHI lọc chữ cái đầu tiên sẽ loại bỏ oan các từ đúng nằm ở vị trí sau 1200 trong từ điển, làm giảm nghiêm trọng độ chính xác của chức năng sửa lỗi.
- **Giải pháp:** Lọc theo chữ cái đầu/gần khớp trước, sau đó mới `slice(0, 300)` để tính khoảng cách Levenshtein.

### 3. Lạm phát độ dài BM25 (Document Length Inflation)
- **Vấn đề:** Hàm `tokenize` hiện tại vừa tách từ vừa expand các từ ghép (như `cict.qt.it` thành `["cict.qt.it", "cict", "qt", "it"]`). Việc này làm tăng độ dài tài liệu ảo (`tokenLength`), khiến BM25 phạt điểm quá nặng các văn bản ngắn chứa nhiều mã hiệu viết tắt.
- **Giải pháp:** Tính độ dài thực tế của tài liệu `tokenLength` dựa trên số lượng token nguyên bản trước khi thực hiện expand từ ghép.

### 4. Highlight không nhất quán (Inconsistent Highlight)
- **Vấn đề:** Regex highlight trong `getSmartSnippet` không ràng buộc biên từ nên dễ bôi đậm sai các từ con nằm trong từ lớn hơn (ví dụ: truy vấn `"an"` làm highlight chữ "an" trong từ `"ban hành"`, `"nhân viên"` vì `â` khớp với pattern không dấu của `a`).
- **Giải pháp:** Áp dụng lookbehind/lookahead phủ định để giả lập ranh giới từ (word boundary) cho cả tiếng Việt có dấu (`vtLettersStr`).

### 5. Stopwords Anh - Việt trùng lắp
- **Vấn đề:** Các từ `"an"`, `"in"`, `"to"` là stopwords tiếng Anh nhưng lại là các từ có nghĩa quan trọng trong tiếng Việt (Ví dụ: `"an toàn"`, `"in ấn"`, `"to lớn"`).
- **Giải pháp:** Loại bỏ hoàn toàn `"an"`, `"in"`, `"to"` ra khỏi bộ lọc `STOP_WORDS` khi phân tích từ tiếng Việt.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> - Thay đổi giải thuật trong `SuperSearch.html` bằng cách viết lại các hàm `getMinSpanProximityBonus`, `getSpellingCorrection`, `prepareDocumentCache`, và regex trong `getSmartSnippet`.
> - Tách biệt đếm từ gốc và lưu token mở rộng.

[ĐỀ_XUẤT_TỐI_ƯU]
- Nâng cấp bộ định nghĩa `STOP_WORDS` chỉ giữ lại các stopwords thực sự vô nghĩa trong cả hai ngôn ngữ.

### Mã giả / Giải thuật đề xuất

#### 1. Đếm độ dài tài liệu chính xác (prepareDocumentCache)
```javascript
// Đếm số token gốc trước khi expand
const rawMatches = cleanText.match(TOKEN_PATTERN) || [];
const rawTokenLength = rawMatches.length;

doc._searchCache = {
    ...
    tokenLength: rawTokenLength || 1, // Tránh lạm phát BM25
    contentTokens: contentTokens // Chứa tokens đã expand phục vụ tìm kiếm
};
```

#### 2. Tối ưu thuật toán Proximity Bonus O(N)
```javascript
function getMinSpanProximityBonus(docCache, queryWords) {
    // 1. Tạo Map tra cứu nhanh từ khóa -> index của query
    // 2. Lặp qua docCache.contentTokens đúng một lần
    // 3. Với mỗi từ khớp, đẩy vị trí của nó vào mảng vị trí tương ứng
    // 4. Thực hiện giải thuật tìm Min-Span sử dụng sliding index
}
```

#### 3. Sửa lỗi lọc Spelling Candidates
```javascript
// Lọc trước khi slice để đảm bảo tính đúng đắn
const matchedCandidates = candidates.filter(vocabWord => {
    return vocabWord.charAt(0) === word.charAt(0) || vocabWord.charAt(1) === word.charAt(1);
});
// Tính Levenshtein chỉ với top 300 ứng viên đã qua bộ lọc
matchedCandidates.slice(0, 300).forEach(vocabWord => {
    ...
});
```

#### 4. Sửa lỗi Highlight bằng biên từ tiếng Việt
```javascript
// Tạo chuỗi ký tự tiếng Việt đầy đủ
const vtLettersStr = "a-zA-Z0-9áàảãạ...";
// Xây dựng regex highlight với lookbehind và lookahead phủ định
const flexRegex = new RegExp('(?<![' + vtLettersStr + '])(' + accentPattern + ')(?![' + vtLettersStr + '])', 'gi');
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. **Kiểm tra độ chính xác tìm kiếm & xếp hạng:** Tìm kiếm từ khóa ghép `"cict.qt.it"` hoặc `"an toàn"`. Đảm bảo tài liệu chứa các từ này xếp lên đầu.
2. **Kiểm tra lỗi highlight:** Tìm kiếm `"an"`. Đảm bảo các từ `"ban hành"`, `"nhân viên"` KHÔNG bị bôi đậm nhầm ký tự `"an"`.
3. **Kiểm tra hiệu năng:** Kiểm tra thời gian tìm kiếm tức thời sau khi cache (tốc độ phản hồi dưới 10ms đối với dữ liệu lớn nhờ thuật toán Proximity O(N) mới).
