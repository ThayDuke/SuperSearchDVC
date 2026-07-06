---
task_name: "Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 3 (Tích hợp toàn diện)"
date: "2026-07-05"
version: "v8"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/data/SuperSearch.html"
---

# Kế hoạch Audit và tối ưu thuật toán tìm kiếm SuperSearch - Lần 3 (Toàn diện)

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> - Tích hợp toàn bộ yêu cầu cải tiến lần 3, nâng cấp đồng bộ cả Backend Python (`app.py`) và Frontend JS (`SuperSearch.html`).
> - Sửa đổi cơ chế quét trích xuất, phân loại nguồn rõ ràng, khắc phục các lỗi logic tìm kiếm, xếp hạng theo ý định tìm kiếm (Intent), sửa lỗi năm mặc định, cải tiến spellcheck, và bảo đảm tính ổn định, tốc độ đạt chuẩn Production.

---

## Phạm vi Thay đổi (Impact Scope)

- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)
- [ ] [MODIFY] [SuperSearch.html](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/data/SuperSearch.html)

---

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)

- Giữ nguyên thiết kế và các trạng thái UI Liquid Glass.
- Giữ nguyên cấu trúc lưu trữ JS offline trong thư mục `data`.
- Không thêm các thư viện phụ trợ nặng làm phình ứng dụng.

---

## Kết quả Đánh giá Thuật toán & Đề xuất (Audit Findings)

### I. Cải tiến Backend Python (`app.py`)

#### 1. Phân loại nguồn (`source_type`) & Đánh giá chất lượng (`ocr_quality_score`)
- **Vấn đề:** Hiện tại, các ảnh chụp màn hình chat hoặc ảnh OCR lỗi nhẹ bị loại thô khỏi index (coi là "Empty/Near Empty" do nhiễu OCR), làm mất thông tin hữu ích.
- **Giải pháp:**
  - Không loại bỏ thô các tệp ảnh/OCR ngoại trừ rác hoàn toàn (quá ít chữ, ký hiệu loạn chiếm >60%).
  - Phân loại nguồn cụ thể (`source_type`):
    - `.pdf`, `.docx`, `.xlsx`, `.doc`, `.xls` -> `formal_document`
    - `.png`, `.jpg`, `.jpeg` chứa các dấu vết chat (ví dụ: `\d{2}:\d{2}`, "tin nhắn", "đã gửi", "hôm qua", "hôm nay", am/pm) -> `chat_screenshot`
    - Có chứa mã nguồn, thẻ HTML/CSS, ký tự lập trình dày đặc -> `ui_screenshot`
    - Các tệp ảnh khác -> `image_ocr`
    - OCR chất lượng rất thấp (nhiều ký tự lạ) -> `low_confidence_ocr`
  - Gán điểm chất lượng `ocr_quality_score` (tỉ lệ từ hợp lệ tiếng Việt/Anh trên tổng số token) để làm trọng số phạt điểm xếp hạng ở frontend thay vì loại bỏ thô.

#### 2. Trích xuất năm chuẩn xác, loại bỏ fallback `2017`
- **Vấn đề:** Hàm `_detect_year` mặc định trả về `2017` khi không tìm thấy năm, làm sai lệch bộ lọc và xếp hạng.
- **Giải pháp:** Tìm kiếm năm theo độ ưu tiên:
  1. Trích xuất từ Tên file (Regex `(201\d|202\d)`).
  2. Trích xuất từ 1000 ký tự đầu tiên của nội dung tài liệu.
  3. Trích xuất từ Metadata hệ thống (`file_year` - năm chỉnh sửa cuối).
  4. Nếu không tìm thấy, gán giá trị `"N/A"`.
  - Frontend JS sẽ cập nhật để hỗ trợ nhóm lọc `"Không rõ năm"`, loại bỏ "N/A" ra khỏi các phép toán tính điểm số học mà xử lý riêng khi sắp xếp.

#### 3. Loại bỏ trùng lặp (De-duplication)
- **Vấn đề:** Các file trùng lặp (nội dung hoặc tiêu đề giống nhau do lưu trữ nhiều nơi) làm rác kết quả tìm kiếm.
- **Giải pháp:**
  - De-dupe cứng theo đường dẫn gốc (`original_path`).
  - De-dupe mềm: Nếu hai tài liệu có cùng Title và kích thước chênh lệch cực nhỏ, hoặc trùng lặp >90% nội dung (băm hash phần đầu nội dung), chỉ giữ lại tài liệu có `ocr_quality_score` cao hơn hoặc file_year mới hơn.

#### 4. Khắc phục nuốt lỗi scan
- **Vấn đề:** Khi một tệp bị lỗi trích xuất hoặc crash converter, app nuốt lỗi im lặng hoặc có nguy cơ ghi dữ liệu lỗi vào index làm hỏng DB.
- **Giải pháp:** Ghi lỗi chi tiết vào một mảng lỗi (file log/trạng thái), bỏ qua file lỗi đó khỏi database index để tránh làm ô nhiễm DB, đảm bảo tiến trình quét đa luồng không bị ngắt quãng.

---

### II. Cải tiến Frontend JS (`SuperSearch.html`)

#### 1. Rút ngắn candidate docs thông qua Inverted Index đa từ
- **Vấn đề:** `getCandidateDocIndexes` trả về OR-match tất cả các tài liệu chứa bất kỳ từ khóa nào, làm giảm hiệu suất khi query dài.
- **Giải pháp:** Chỉ lấy các tài liệu có số từ khớp tối thiểu (Query có 1-2 từ: tối thiểu khớp 1 từ; Query >=3 từ: tối thiểu khớp 2 từ hoặc 40% số từ).

#### 2. Sửa lỗi so khớp Substring thô (False Substring Match)
- **Vấn đề:** Dùng `includes` làm từ khóa ngắn match nhầm substring trong từ dài (ví dụ `"an"` match `"ban"`).
- **Giải pháp:** Tạo hàm `includesWholeWord` dùng vị trí ký tự biên từ tiếng Việt (`isWholeWord`) để so khớp chính xác từ nguyên vẹn.

#### 3. Sửa lỗi lệch vị trí Snippet (Snippet Offset Shift)
- **Vấn đề:** Chuẩn hóa NFD làm thay đổi độ dài chuỗi sạch, khiến vị trí cắt snippet bị lệch khi cắt trên chuỗi gốc.
- **Giải pháp:** Thay thế giải thuật `removeDiacritics` bằng ánh xạ tĩnh 1-1 ký tự tiếng Việt có dấu sang không dấu thường, bảo toàn độ dài chuỗi gốc 100%.

#### 4. Tách biệt hoàn toàn filterQuery
- **Giải pháp:** Đảm bảo `filterQuery` chỉ lọc cứng kết quả sau khi ranking, không tham gia tính toán BM25 scoring.

#### 5. Nâng cấp Ranking theo Ý định (Intent-based Ranking)
- Phân tích Query:
  - Nếu query chứa từ khóa chính sách, quy chế, quy trình, hướng dẫn (`policy`, `procedure`, `quy dinh`, `huong dan`) -> Boost mạnh cho `source_type === "formal_document"`.
  - Nếu query chứa số tiền, tên người, câu nói, từ thông tục chat (`tăng lương`, `thưởng`, `chúc mừng`, số tiền `tr`, `triệu`) -> Boost mạnh cho `source_type === "chat_screenshot"`.
  - Nếu query là mã tài liệu hoặc từ khóa viết tắt (`CICT.CS.IT-01`) -> Ưu tiên tuyệt đối exact title match hoặc exact code match.
- Áp dụng hình phạt điểm (penalty) dựa trên `ocr_quality_score` thấp (dưới 0.7) để đẩy các kết quả OCR nhiễu xuống dưới, nhưng không loại bỏ thô.

#### 6. Nâng cấp Spellcheck thông minh
- Cấm tự động sửa các từ viết tắt chuyên ngành (acronyms) như: `IT`, `HR`, `KPI`, `HSSE`, `HSSEQ`.
- Cấm tự động sửa các từ chứa ký tự đặc biệt dạng mã tài liệu (ví dụ chứa dấu gạch ngang, dấu chấm).
- Chỉ hiển thị hoặc tự động thay thế khi điểm tin cậy sửa lỗi cực cao. Không tự động thay đổi query khi kết quả tìm kiếm gốc vẫn có ích.

#### 7. Tối ưu hóa tốc độ
- Áp dụng Lazy Cache khi truy vấn: Chỉ sinh cache tìm kiếm chi tiết (`prepareDocumentCache`) cho các Candidate Documents thực sự cần xếp hạng thay vì tính toán trước toàn bộ DB lúc khởi động.
- Giới hạn highlight chỉ cho các kết quả đang hiển thị trên trang hiện tại.

---

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> - Sửa đổi hàm trong Python backend (`app.py`) cho trích xuất năm và phân loại nguồn.
> - Cải tiến toàn diện thuật toán client-side trong `SuperSearch.html`.

### Mã giả / Giải thuật đề xuất (Backend Python)

#### 1. Trích xuất năm chuẩn hóa và source_type
```python
def _detect_year(self, content_lower, filename):
    # 1. Tên file
    year_match = re.search(r'\b(201\d|202\d)\b', filename)
    if year_match:
        return int(year_match.group(1))
    # 2. 1000 ký tự đầu
    first_part = content_lower[:1000]
    years = re.findall(r'\b(201\d|202\d)\b', first_part)
    if years:
        return int(max(set(years), key=years.count))
    # 3. File Metadata
    # 4. Fallback "N/A"
    return "N/A"

def _classify_source(self, filepath, rel_path, content):
    content_lower = content.lower()
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext in ['.pdf', '.docx', '.xlsx', '.doc', '.xls']:
        return "formal_document"
        
    if ext in ['.png', '.jpg', '.jpeg']:
        # Kiểm tra vết chat
        chat_patterns = [r'\d{2}:\d{2}', 'đã gửi', 'tin nhắn', 'hôm qua', 'hôm nay']
        if any(re.search(p, content_lower) for p in chat_patterns):
            return "chat_screenshot"
            
        # Kiểm tra code/UI
        ui_patterns = [r'class\s+\w+', r'import\s+\w+', r'const\s+\w+', r'<\/div>', r'<html>']
        if any(re.search(p, content_lower) for p in ui_patterns):
            return "ui_screenshot"
            
        return "image_ocr"
        
    return "formal_document"
```

### Mã giả / Giải thuật đề xuất (Frontend JS)

#### 1. Tìm kiếm Candidate tối ưu và Xếp hạng Intent
```javascript
function getCandidateDocIndexes(uniqueSearchWords) {
    if (!uniqueSearchWords || uniqueSearchWords.length === 0) return null;
    const docMatchCounts = new Map();
    
    uniqueSearchWords.forEach(word => {
        const directMatches = searchTokenDocs.get(word);
        if (directMatches) {
            directMatches.forEach(idx => {
                docMatchCounts.set(idx, (docMatchCounts.get(idx) || 0) + 1);
            });
        }
    });
    
    const minMatches = uniqueSearchWords.length <= 2 ? 1 : Math.max(2, Math.ceil(uniqueSearchWords.length * 0.4));
    const candidateIndexes = new Set();
    for (const [idx, count] of docMatchCounts.entries()) {
        if (count >= minMatches) {
            candidateIndexes.add(idx);
        }
    }
    return candidateIndexes;
}

function searchDatabase(searchTerm, searchWords) {
    // ...
    candidateDocs.forEach(doc => {
        let score = calculateBM25AndProximity(doc, searchWords);
        
        // 1. Phạt điểm OCR chất lượng thấp
        if (doc.ocr_quality_score && doc.ocr_quality_score < 0.7) {
            score *= doc.ocr_quality_score;
        }
        
        // 2. Phân tích Intent và Boost điểm
        const queryLower = searchTerm.toLowerCase();
        if (doc.source_type === "formal_document" && (queryLower.includes("chinh sach") || queryLower.includes("quy trinh"))) {
            score += 300;
        } else if (doc.source_type === "chat_screenshot" && (queryLower.includes("tang luong") || queryLower.includes("chuc mung") || /\d+/.test(queryLower))) {
            score += 300;
        }
        
        // ...
    });
}
```

---

## Kế hoạch Kiểm thử & Xác minh (Verification Plan)

### Kiểm thử Thủ công (QA Steps)
1. **Tìm kiếm mã tài liệu chính xác:** Tìm `"CICT.CS.IT-01"`. Kết quả đứng đầu bảng phải là tài liệu chính thống có mã này.
2. **Tìm kiếm từ khóa chat:** Tìm `"tăng 7tr"`. Kết quả ảnh chụp chat phải được xếp hạng cao lên top.
3. **Bộ lọc năm và N/A:** Lọc nhóm `"Không rõ năm"`. Đảm bảo các tài liệu không trích xuất được năm sẽ hiển thị đúng trong nhóm này.
4. **Kiểm tra Spellcheck:** Gõ `"CICT.CS.IT"`. Spellcheck tuyệt đối không được tự ý sửa hoặc gợi ý sai lệch từ khóa này.
