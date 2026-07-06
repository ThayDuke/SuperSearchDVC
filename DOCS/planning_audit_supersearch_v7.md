---
task_name: "Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 3"
date: "2026-07-05"
version: "v7"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 3

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Đánh giá chuyên sâu thuật toán tìm kiếm client-side của SuperSearch.
> - Khắc phục các lỗi: quét tuyến tính diện rộng, match substring sai lệch điểm, lệch snippet do normalize, lỗi spellcheck thiếu từ vựng content, và tách biệt filterQuery.
> - Đảm bảo độ chính xác xếp hạng BM25 + Proximity, độ ổn định tuyệt đối chuẩn Production.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên cấu trúc dữ liệu chính trong `search_db.js`.
- Giữ nguyên các thành phần giao diện Liquid Glass.
- Không thay đổi backend PyWebView/Python.

---

## Kết quả Đánh giá Thuật toán & Đề xuất (Audit Findings)

### 1. Rút ngắn candidate docs thông qua Inverted Index lọc đa từ (Multi-term Filtering)
- **Vấn đề:** Hiện tại `getCandidateDocIndexes` trả về bất kỳ tài liệu nào chứa dù chỉ một từ khóa (OR match). Khi query dài, số lượng candidates quá lớn làm mất ý nghĩa của Inverted Index.
- **Giải pháp:** Đếm số từ khóa khớp cho mỗi tài liệu. Chỉ đưa vào candidates những tài liệu chứa số lượng từ khóa tối thiểu (ví dụ: tối thiểu khớp 2 từ hoặc 40% số từ khóa với query dài).

### 2. Sửa lỗi so khớp Substring thô (False Substring Match)
- **Vấn đề:** Dùng `includes` trực tiếp khiến từ khóa ngắn (như `"an"`) khớp với các từ lớn hơn (như `"ban"`, `"lan"`), gây lạm phát điểm xếp hạng.
- **Giải pháp:** Xây dựng hàm `includesWholeWord` sử dụng kiểm tra biên từ tiếng Việt bằng Regex hoặc kiểm tra vị trí ký tự biên (`isWholeWord`), loại bỏ match nhiễu.

### 3. Sửa lỗi lệch vị trí Snippet (Snippet Offset Shift)
- **Vấn đề:** Sử dụng NFD normalization thay đổi độ dài chuỗi khiến chỉ số vị trí cắt (`bestIndex`) trong chuỗi sạch bị lệch khi cắt trên chuỗi gốc, dẫn đến mất chữ hoặc cụt snippet.
- **Giải pháp:** Viết lại hàm `removeDiacritics` sử dụng bảng ánh xạ 1-1 ký tự có dấu sang không dấu thường, bảo toàn độ dài chuỗi gốc 100%.

### 4. Tăng cường Từ vựng Autocorrect từ Content (Content-aware Spellcheck)
- **Vấn đề:** Bộ từ vựng gợi ý chính tả chỉ lấy từ Title và Metadata, bỏ qua Content nên hệ thống sẽ tự động sửa các từ đúng trong Content thành từ sai.
- **Giải pháp:** Nạp thêm các từ hợp lệ (độ dài >=3, không chứa số/ký tự đặc biệt) từ `cache.termKeys` (Content) vào vocabulary, áp dụng giới hạn tối ưu hiệu năng.

### 5. Tách biệt hoàn toàn filterQuery
- **Vấn đề:** Đảm bảo `filterQuery` không bao giờ bị đưa vào xếp hạng điểm BM25 mà chỉ được dùng làm bộ lọc cứng (hard filter) sau khi xếp hạng.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> - Nâng cấp thuật toán client-side trong `SuperSearch.html`.
> - Tối ưu hóa các hàm lõi: `removeDiacritics`, `getCandidateDocIndexes`, `searchDatabase`, `getSmartSnippet`.

[ĐỀ_XUẤT_TỐI_ƯU]
- Áp dụng ánh xạ tĩnh 1-1 cho `removeDiacritics` thay thế toàn bộ regex NFD.

### Mã giả / Giải thuật đề xuất

#### 1. Ánh xạ 1-1 bảo toàn độ dài (removeDiacritics)
```javascript
function removeDiacritics(str) {
    if (!str) return "";
    const map = { /* Bảng map ký tự có dấu -> không dấu */ };
    let res = "";
    for (let i = 0; i < str.length; i++) {
        const char = str.charAt(i);
        res += map[char] || char.toLowerCase();
    }
    return res;
}
```

#### 2. Lọc Candidate thông minh (getCandidateDocIndexes)
```javascript
function getCandidateDocIndexes(uniqueSearchWords) {
    if (!uniqueSearchWords || uniqueSearchWords.length === 0) return null;
    const docMatchCounts = new Map();
    uniqueSearchWords.forEach(word => {
        const directMatches = searchTokenDocs.get(word);
        if (directMatches) {
            directMatches.forEach(idx => docMatchCounts.set(idx, (docMatchCounts.get(idx) || 0) + 1));
        }
        // Fallback expand token if length >= 3 ...
    });
    
    const minMatches = uniqueSearchWords.length <= 2 ? 1 : Math.max(2, Math.ceil(uniqueSearchWords.length * 0.4));
    const candidateIndexes = new Set();
    for (const [idx, count] of docMatchCounts) {
        if (count >= minMatches) candidateIndexes.add(idx);
    }
    return candidateIndexes;
}
```

#### 3. So khớp từ nguyên vẹn (includesWholeWord)
```javascript
function includesWholeWord(text, word) {
    let pos = text.indexOf(word);
    const wordLen = word.length;
    while (pos !== -1) {
        if (isWholeWord(text, pos, wordLen)) return true;
        pos = text.indexOf(word, pos + 1);
    }
    return false;
}
```

#### 4. Nạp từ vựng Content (buildSearchIndex)
```javascript
function buildSearchIndex() {
    // ... Khởi tạo ...
    SEARCH_DB.forEach((doc, docIndex) => {
        const cache = prepareDocumentCache(doc);
        // Nạp thêm vocab từ content (termKeys)
        cache.termKeys.forEach(token => {
            if (token.length >= 3 && /^[a-z]+$/.test(token)) {
                addVocabularyToken(token);
            }
        });
    });
}
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. **Kiểm tra độ chính xác xếp hạng:** Tìm kiếm cụm từ `"an toàn lao động"` hoặc `"cict.qt.it"`. Đảm bảo các tài liệu khớp chính xác các từ trên đứng đầu bảng.
2. **Kiểm tra biên độ highlight và snippet:** Đảm bảo snippet hiển thị đúng vị trí chứa từ khóa, không bị lệch hoặc mất chữ đầu do normalize.
3. **Kiểm thử hiệu năng:** Thực hiện tìm kiếm nhiều lần với các query khác nhau để kiểm chứng việc rút ngắn thời gian xử lý nhờ Inverted Index và Proximity O(N).
