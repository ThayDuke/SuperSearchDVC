---
task_name: "Audit và tối ưu thuật toán tìm kiếm SuperSearch"
date: "2026-07-05"
version: "v4"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Audit và tối ưu thuật toán tìm kiếm SuperSearch

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Đánh giá chi tiết thuật toán tìm kiếm vừa nâng cấp.
> - Phát hiện các lỗi logic, hiệu năng và đề xuất tối ưu.
> - Thực hiện quy trình lập kế hoạch `/pl`.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên cấu trúc dữ liệu chính trong `search_db.js`.
- Giữ nguyên các cấu trúc giao diện UI Liquid Glass.
- Không thay đổi các phương thức OCR trong Python.

---

## Kết quả Đánh giá Thuật toán (Audit Findings)

### 1. Hiệu năng Proximity Bonus (Nghiêm trọng)
- Hàm `getMinSpanProximityBonus` chạy `tokenize` trực tiếp cho 80 file hàng đầu mỗi lượt tìm kiếm.
- Mỗi lần `tokenize` lại gọi `removeDiacritics` trên văn bản thô cực lớn, gây đơ giao diện.

### 2. Xung đột Stopwords Anh - Việt (Nghiêm trọng)
- `STOP_WORDS` chứa các từ tiếng Anh: `"an"`, `"in"`, `"on"`, `"to"`.
- Trong tiếng Việt, các từ này có nghĩa quan trọng: `"an"` (an toàn), `"in"` (in ấn), `"to"` (to lớn).
- Hệ quả: Tìm kiếm cụm từ `"an toàn"` bị lọc mất chữ `"an"`, làm sai lệch kết quả nghiêm trọng.

### 3. Lọc nhiễu OCR quá đà ở Backend
- Hàm `_is_ocr_noise` ở Python tự động bỏ qua file nếu từ `< 15` và ký tự `|` > 5.
- Lỗi: Loại bỏ oan các bảng biểu ngắn, bìa hồ sơ, form thông tin hợp lệ.

### 4. Lạm phát độ dài BM25 (Document Length Inflation)
- Việc mở rộng từ ghép (ví dụ `cict.qt.it` thành 4 từ) làm tăng chiều dài tài liệu ảo.
- Hệ quả: Làm giảm điểm BM25 của tài liệu chứa nhiều từ ghép do cơ chế phạt độ dài tài liệu.

### 5. Inconsistent Highlight
- `getSmartSnippet` sử dụng regex không ràng buộc biên chữ `vtLetters`, gây highlight lộn xộn.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> - Cải tiến lưu trữ cache token trực tiếp để triệt tiêu thời gian tokenize lúc tìm kiếm.
> - Tách biệt và chuẩn hóa stopwords Việt - Anh tránh lọc nhầm từ quan trọng.
> - Điều chỉnh tham số lọc nhiễu ở Python backend để giữ lại bảng biểu ngắn.

[ĐỀ_XUẤT_TỐI_ƯU]
- Lưu `contentTokens` vào `_searchCache` khi build index một lần duy nhất.
- Loại bỏ `"an"`, `"in"`, `"to"` khỏi `STOP_WORDS` của tiếng Việt.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Caching `contentTokens` sẽ tăng sử dụng RAM ở client khoảng 5-10MB.
> - Đây là mức chấp nhận được để đạt tốc độ tìm kiếm tức thời < 10ms.

### Mã giả / Giải thuật đề xuất

#### 1. Caching tokens trong SuperSearch.html
```javascript
// Thay đổi trong prepareDocumentCache
doc._searchCache = {
    ...
    contentTokens: contentTokens // Thay vì null
};

// Thay đổi trong getMinSpanProximityBonus
const wordsInDoc = docCache.contentTokens || tokenize(docCache.contentText);
```

#### 2. Lọc Stopwords thông minh
```javascript
// Loại bỏ các từ trùng tiếng Việt khỏi STOP_WORDS
const STOP_WORDS = new Set([
    "with", "of", "the", "and", "at", "for", "a",
    "va", "cua", "nhung", "cac", "cho", "trong", "tren", "tai", "la", "duoc"
]);
```

#### 3. Điều chỉnh ngưỡng nhiễu OCR trong app.py
```python
# Tăng điều kiện lọc nhiễu OCR để tránh mất bảng biểu
if len(words) < 8 and (pipes > 8 or symbols / total_len > 0.4):
    return True
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. Quét lại thư mục dữ liệu, kiểm tra xem các file bảng biểu ngắn có bị bỏ sót không.
2. Tìm kiếm `"an toàn"` và xác nhận từ khóa `"an"` được bôi đậm chính xác, xếp hạng HSSE lên đầu.
3. Đo thời gian tìm kiếm với từ khóa phổ biến (phải dưới 15ms nhờ cache tokens).
