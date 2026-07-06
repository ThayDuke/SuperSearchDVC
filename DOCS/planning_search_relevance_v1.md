---
task_name: "Cải thiện độ chính xác tìm kiếm cụm từ"
date: "2026-07-02"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Cải thiện độ chính xác tìm kiếm cụm từ (Fuzzy Phrase Matching)

Sửa lỗi tìm kiếm cụm từ có chứa từ thừa ở giữa (ví dụ: tìm "mình đã nghi rồi" nhưng trong văn bản là "mình đã nghi nghi rồi") không được ưu tiên lên đầu.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Hàm `searchDatabase`: Giữ nguyên cấu trúc tính điểm từ đơn lẻ và điểm xếp hạng theo metadata (năm, loại văn bản, v.v.).

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Hàm phụ trợ kiểm tra khớp từ theo thứ tự
```javascript
function matchesInOrder(text, words) {
    if (words.length < 2) return false;
    const escaped = words.map(w => w.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'));
    const pattern = escaped.join('.*?');
    const regex = new RegExp(pattern, 'i');
    return regex.test(text);
}

function hasInOrderSentenceMatch(contentCleanedLower, queryWords) {
    if (queryWords.length < 2) return false;
    const sentences = contentCleanedLower.split(/[.!?\n]/);
    return sentences.some(sentence => matchesInOrder(sentence, queryWords));
}
```

### 2. Tích hợp điểm thưởng vào logic `searchDatabase()`
Trong `searchDatabase()`:
- Đổi điểm thưởng khớp cụm từ chính xác (`cleanContent.includes(searchTerm)`) thành `+300`.
- Nếu không khớp chính xác nhưng khớp theo thứ tự trong cùng một câu (`hasInOrderSentenceMatch(cleanContent, searchWords)`), cộng điểm thưởng `+200`.

## Quy chuẩn hiển thị Alerts

> [!TIP]
> [HIỂU_YÊU_CẦU]
> Nhận diện tài liệu có cụm từ khớp một phần hoặc khớp mờ (fuzzy) có các từ phụ ở giữa.
> Tăng thứ hạng các tài liệu này vượt lên trên các tài liệu lớn chỉ chứa các từ khóa rời rạc.
> Độ tự tin: 10/10.

> [!NOTE]
> [PHƯƠNG_PHÁP]
> Thêm thuật toán kiểm tra thứ tự từ xuất hiện trong câu (Regex `word1.*?word2.*?word3`).
> Cộng điểm thưởng lớn (+200) cho tài liệu đạt điều kiện này.

[ĐỀ_XUẤT_TỐI_ƯU]
- Nâng điểm cộng cụm từ chính xác lên +300 để đảm bảo phân tách rõ ràng độ ưu tiên (Khớp chính xác > Khớp mờ có thứ tự > Khớp từ rời rạc).

> [!WARNING]
> [CẢNH_BÁO]
> Việc dùng biểu thức chính quy (Regex) và tách câu trên tập dữ liệu lớn có thể ảnh hưởng nhỏ đến hiệu năng.
> Đã xử lý: Chỉ chạy kiểm tra này khi tài liệu đã khớp đủ 100% số lượng từ khóa trong câu truy vấn.

[NEO_HỒI_QUY]
- Giữ nguyên cơ chế chấm điểm từ khóa đơn lẻ.
- Giữ nguyên các điểm cộng khác (năm phát hành, file ký duyệt, v.v.).
