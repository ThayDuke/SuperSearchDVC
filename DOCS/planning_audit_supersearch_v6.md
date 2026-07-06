---
task_name: "Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 2 (Tích hợp nguồn audit bổ sung)"
date: "2026-07-05"
version: "v6"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 2 (Tích hợp)

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Tích hợp đầy đủ các phát hiện audit từ cả hai nguồn (bao gồm: quét tuyến tính, match substring lỗi, lạm phát BM25, highlight lỗi, lỗi lệch snippet, filter query bị tính điểm 2 lần, và autocorrect yếu).
> - Xây dựng giải thuật tối ưu toàn diện, an toàn cho Production.
> - Đảm bảo tính tương thích và bảo lưu giao diện hiện tại cùng logic OCR của backend.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên cấu trúc dữ liệu chính trong `search_db.js`.
- Giữ nguyên thiết kế và các trạng thái UI Liquid Glass.
- Không thay đổi các phương thức OCR trong Python backend.
- Giữ nguyên các hàm API giao tiếp với PyWebView.

---

## Kết quả Đánh giá Thuật toán & Đề xuất (Audit Findings)

### 1. Quét tuyến tính toàn bộ tài liệu (Mới phát hiện)
- **Vấn đề:** Mỗi lần tìm kiếm, hệ thống lặp qua toàn bộ `SEARCH_DB` (quét tuyến tính). Khi số lượng tài liệu tăng lên, hiệu năng sẽ bị nghẽn nghiêm trọng.
- **Giải pháp:** Xây dựng cấu trúc **Inverted Index** ở client-side trong quá trình chuẩn bị dữ liệu (`buildSearchIndex`). Khi tìm kiếm, chỉ cần truy vấn Inverted Index để lấy tập hợp các tài liệu chứa từ khóa (Candidate Docs), tránh duyệt tuyến tính qua các tài liệu không liên quan.

### 2. Match Substring gây nhiễu điểm số (Mới phát hiện)
- **Vấn đề:** Việc dùng `includes` trực tiếp để so khớp từ khóa phụ (`cleanContent.includes(word)`) làm match nhầm các từ con nằm trong từ lớn hơn (ví dụ `"an"` khớp với `"ban"`), dẫn đến lạm phát điểm ranking sai lệch.
- **Giải pháp:** Sử dụng so khớp từ nguyên vẹn thông qua Token Set hoặc Regex giả lập biên từ tiếng Việt (`(?<![vtLetters])word(?![vtLetters])`) thay vì `includes` thô.

### 3. Snippet bị lệch vị trí cắt do Normalize (Mới phát hiện)
- **Vấn đề:** Khi `getSmartSnippet` sử dụng `removeDiacritics` (loại bỏ dấu bằng NFD và regex), chuỗi bị giảm độ dài. Việc cắt snippet dựa trên index của chuỗi đã chuẩn hóa lên chuỗi gốc sẽ bị lệch vị trí (mất chữ, mất ngữ cảnh).
- **Giải pháp:** Viết hàm `removeDiacriticsKeepLength` ánh xạ 1-1 các ký tự có dấu sang không dấu để độ dài chuỗi sau chuẩn hóa hoàn toàn bằng chuỗi gốc.

### 4. Filter Query bị tính điểm hai lần (Mới phát hiện)
- **Vấn đề:** Từ khóa lọc (`filterQuery`) được đưa vào `searchWords` để chạy scoring BM25/IDF chung với từ khóa chính, làm nhiễu xếp hạng chính.
- **Giải pháp:** Tách biệt hoàn toàn `filterQuery` khỏi phần scoring chính. Chỉ dùng `filterQuery` ở bước lọc kết quả cuối cùng.

### 5. Từ vựng Autocorrect thiếu sót & Stopwords bị xóa oan
- **Vấn đề:** Từ vựng sửa lỗi chính tả chỉ nạp từ Title và Metadata, thiếu từ trong Content. Đồng thời `"an"`, `"in"`, `"to"` bị lọc mất do stopwords tiếng Anh trùng lặp.
- **Giải pháp:** Đưa các từ có nghĩa từ Content vào bộ từ vựng, lọc candidates trước khi so sánh khoảng cách Levenshtein và loại bỏ các từ Việt quan trọng ra khỏi danh sách stopwords.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> - Nâng cấp toàn diện các hàm trong `SuperSearch.html`.
> - Tích hợp Inverted Index và tối ưu Proximity O(N).

[ĐỀ_XUẤT_TỐI_ƯU]
- Lưu Inverted Index client-side dạng `Map<string, Document[]>` để truy xuất nhanh tức thì.

### Mã giả / Giải thuật đề xuất

#### 1. Xây dựng Inverted Index (buildSearchIndex)
```javascript
let invertedIndex = new Map();

function buildSearchIndex() {
    invertedIndex = new Map();
    SEARCH_DB.forEach(doc => {
        const cache = prepareDocumentCache(doc);
        const uniqueDocTokens = new Set([...cache.titleTokenSet, ...cache.metadataTokenSet, ...cache.termKeys]);
        
        uniqueDocTokens.forEach(token => {
            if (!invertedIndex.has(token)) {
                invertedIndex.set(token, []);
            }
            invertedIndex.get(token).push(doc);
        });
    });
}
```

#### 2. Rút gọn tập tìm kiếm bằng Inverted Index (searchDatabase)
```javascript
function searchDatabase(searchTerm, searchWords) {
    let docsToSearch = SEARCH_DB;
    if (searchWords.length > 0) {
        const candidateSet = new Set();
        searchWords.forEach(word => {
            const list = invertedIndex.get(word);
            if (list) {
                list.forEach(doc => candidateSet.add(doc));
            }
        });
        docsToSearch = Array.from(candidateSet);
    }
    // Thực hiện tính BM25 và scoring trên docsToSearch thay vì toàn bộ SEARCH_DB
}
```

#### 3. Chuẩn hóa so khớp biên từ tiếng Việt
```javascript
const vtLettersStr = "a-zA-Z0-9áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ";

// Khi so khớp substring phụ trợ:
const wordPattern = new RegExp('(?<![' + vtLettersStr + '])' + escapeRegex(word) + '(?![' + vtLettersStr + '])', 'i');
if (wordPattern.test(cleanContent)) { ... }
```

#### 4. Ánh xạ chuẩn hóa 1-1 giữ nguyên độ dài cho Snippet
```javascript
function removeDiacriticsKeepLength(str) {
    // Sử dụng bảng map ký tự có dấu trực tiếp sang không dấu
    // Đảm bảo kết quả trả về có độ dài khớp 100% với chuỗi gốc
}
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. **Kiểm tra độ chính xác xếp hạng:** Tìm kiếm cụm từ `"an toàn lao động"` hoặc `"cict.qt.it"`. Đảm bảo tài liệu khớp chính xác đứng đầu bảng.
2. **Kiểm tra biên độ highlight và snippet:** Đảm bảo snippet hiển thị đúng vị trí chứa từ khóa, không bị lệch hoặc mất chữ đầu do normalize.
3. **Kiểm thử hiệu năng:** Thực hiện tìm kiếm nhiều lần với các query khác nhau để kiểm chứng việc rút ngắn thời gian xử lý nhờ Inverted Index và Proximity O(N).
