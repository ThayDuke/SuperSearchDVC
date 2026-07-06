---
task_name: "Tối ưu thuật toán tìm kiếm và xếp hạng chuyên nghiệp"
date: "2026-07-02"
version: "v2"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Tối ưu thuật toán tìm kiếm và xếp hạng chuyên nghiệp (BM25 & Whole-Word Matching)

Giải quyết triệt để vấn đề tài liệu nhỏ chứa từ khóa cô đọng bị đẩy tụt xuống dưới các tài liệu lớn chứa từ khóa rời rạc. Xử lý triệt để việc tìm kiếm từ ngắn khớp nhầm các từ dài hơn và highlight lỗi.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Hàm `searchDatabase`: Điều chỉnh cách tính điểm cho mỗi từ khóa và cơ chế cộng điểm thưởng.
- Hàm `highlightText` và `highlightElementTextNodes`: Giữ nguyên cấu trúc đệ quy/regex nhưng tối ưu biểu thức chính quy để chỉ highlight từ khớp hoàn toàn.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Hàm bổ trợ phân biệt Từ khớp hoàn toàn (Whole Word)
```javascript
function isWholeWord(text, pos, wordLen) {
    const prevChar = pos > 0 ? text.charAt(pos - 1) : ' ';
    const nextChar = pos + wordLen < text.length ? text.charAt(pos + wordLen) : ' ';
    const isAlphaNum = (char) => /[a-z0-9]/i.test(char);
    return !isAlphaNum(prevChar) && !isAlphaNum(nextChar);
}
```

### 2. Thuật toán BM25 & Phân bổ Trọng số trong `searchDatabase()`
- Khởi tạo tính toán độ dài từ của mỗi tài liệu trên startup: `doc.wordCount = doc.content ? doc.content.split(/\s+/).length : 1;`.
- Tính độ dài trung bình tài liệu `averageDocLength`.
- Khi tính tần suất xuất hiện từ (`tf`):
  - Khớp nguyên từ: Trọng số = `1.0`.
  - Khớp một phần (substring): Trọng số = `0.15` (phạt 85%).
- Áp dụng công thức chuẩn hóa độ dài BM25 ($k_1 = 1.2, b = 0.75$) để triệt tiêu lợi thế của tài liệu quá dài.

### 3. Tối ưu hóa Highlight chỉ khớp nguyên từ
Sử dụng biểu thức chính quy với Lookbehind `(?<!...)` và Lookahead `(?!...)` dựa trên bảng chữ cái tiếng Việt mở rộng để tránh highlight một phần từ (ví dụ: gõ "đã" không highlight "đạ" trong "đạt").
```javascript
const vtLetters = '[a-zA-Z0-9áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ]';
const flexRegex = new RegExp('(?<!' + vtLetters + ')(' + accentPattern + ')(?!' + vtLetters + ')', 'gi');
```

## Quy chuẩn hiển thị Alerts

> [!TIP]
> [HIỂU_YÊU_CẦU]
> Tách biệt điểm số giữa khớp nguyên từ (Whole Word) và khớp một phần (Substring).
> Bình thường hóa độ dài văn bản (Length Normalization) bằng thuật toán BM25 để ưu tiên các file nhỏ gọn chứa từ khóa đậm đặc (như png.jpg).
> Sửa lỗi highlight đè lên từ dài hơn.
> Độ tự tin: 10/10.

> [!NOTE]
> [PHƯƠNG_PHÁP]
> Thêm bộ đếm wordCount cho mỗi doc và averageDocLength trong `window.onload`.
> Sử dụng kỹ thuật Regex Unicode Lookaround cho cả hàm highlight trong chat và popup.

[ĐỀ_XUẤT_TỐI_ƯU]
- Áp dụng hệ số phạt 85% cho các từ khớp một phần giúp triệt tiêu điểm số ảo từ các từ ghép trùng ký tự đầu.

> [!WARNING]
> [CẢNH_BÁO]
> Độ dài trung bình tài liệu cần được tính toán động khi khởi chạy app để có kết quả chính xác nhất trên cơ sở dữ liệu thực tế.

[NEO_HỒI_QUY]
- Giữ nguyên các logic lọc dropdown và lọc phụ sau khi tìm kiếm.
