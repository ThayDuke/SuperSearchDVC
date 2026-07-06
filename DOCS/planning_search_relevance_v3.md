---
task_name: "Phạt substring và tối ưu khoảng cách từ khóa (Min-Span)"
date: "2026-07-02"
version: "v3"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/SuperSearch.html"
---

# Tối ưu khoảng cách từ khóa (Min-Span Proximity) và Phạt Substring mạnh hơn

Giải quyết triệt để lỗi tài liệu lớn chiến thắng tài liệu nhỏ nhờ ghép từ khóa rác và cải thiện tính toán khoảng cách từ khóa thực tế thay vì dựa vào ranh giới câu cứng nhắc.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/SuperSearch.html)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Hàm `searchDatabase`: Thay thế hàm tính `getProximityBonus` bằng `getMinSpanProximityBonus` thông minh hơn.
- Trọng số phạt khớp một phần: Giảm từ `0.15` xuống `0.02` (phạt 98%).

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Thuật toán Min-Span Proximity
Tính toán khoảng cách ngắn nhất (Word Span) chứa toàn bộ các từ khóa đã khớp trong tài liệu.
```javascript
function getMinSpanProximityBonus(contentCleanedLower, queryWords) {
    if (queryWords.length < 2) return 0;
    const wordsInDoc = contentCleanedLower.split(/\s+/).filter(w => w.length > 0);
    const wordPositions = [];
    
    queryWords.forEach(qWord => {
        const positions = [];
        wordsInDoc.forEach((docWord, idx) => {
            if (docWord === qWord || docWord.includes(qWord)) {
                positions.push(idx);
            }
        });
        if (positions.length > 0) {
            wordPositions.push(positions);
        }
    });

    const matchedWordCount = wordPositions.length;
    if (matchedWordCount < 2) return 0;

    let minSpan = Infinity;
    const indices = new Array(matchedWordCount).fill(0);
    
    while (true) {
        let minVal = Infinity;
        let maxVal = -Infinity;
        let minIdx = -1;
        for (let i = 0; i < matchedWordCount; i++) {
            const val = wordPositions[i][indices[i]];
            if (val < minVal) { minVal = val; minIdx = i; }
            if (val > maxVal) maxVal = val;
        }
        const currentSpan = maxVal - minVal + 1;
        if (currentSpan < minSpan) minSpan = currentSpan;
        indices[minIdx]++;
        if (indices[minIdx] >= wordPositions[minIdx].length) break;
    }

    const density = matchedWordCount / minSpan;
    const matchRatio = matchedWordCount / queryWords.length;
    return matchRatio * density * 250;
}
```

### 2. Tích hợp trong `searchDatabase()`
- Thay `score += getProximityBonus(...)` bằng `score += getMinSpanProximityBonus(...)`.
- Đổi trọng số cộng cho substring match:
```javascript
if (isWholeWord(cleanContent, pos, word.length)) {
    matchWeightSum += 1.0;
} else {
    matchWeightSum += 0.02; // Phạt 98% cho khớp một phần
}
```

## Quy chuẩn hiển thị Alerts

> [!TIP]
> [HIỂU_YÊU_CẦU]
> Tăng cường phạt khớp một phần (từ 0.15 xuống 0.02) để loại bỏ điểm ảo của tài liệu lớn chứa hậu tố/tiền tố trùng lặp.
> Áp dụng thuật toán Min-Span Proximity tính mật độ từ khóa giúp ưu tiên tuyệt đối các tài liệu chứa các từ khóa tập trung sát nhau (như png.jpg).
> Độ tự tin: 10/10.

> [!NOTE]
> [PHƯƠNG_PHÁP]
> Thay thế toàn bộ logic phân tách câu của `getProximityBonus` bằng `getMinSpanProximityBonus`.
> Giảm hệ số cộng của substring xuống còn 0.02.

[ĐỀ_XUẤT_TỐI_ƯU]
- Min-Span giải quyết được việc các từ khóa bị ngăn cách bởi dấu xuống dòng hoặc ký tự đặc biệt vẫn được tính gần nhau nếu chúng nằm trong cùng đoạn hội thoại ngắn.

> [!WARNING]
> [CẢNH_BÁO]
> Không có. Hiệu năng của thuật toán con trỏ đuổi trên mảng chỉ số (Min-Span) là cực kỳ nhanh ($O(N)$ với $N$ là tổng số vị trí khớp).

[NEO_HỒI_QUY]
- Giữ nguyên cơ chế BM25 và các logic highlight từ.
