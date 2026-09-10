---
title: "Kế hoạch handoff remaster tìm kiếm SuperSearch v1"
version: "v1"
status: "IMPLEMENTED"
mode: "handoff"
workflow: "/ho"
created: "2026-09-01"
risk_level: "HIGH"
executor_target: "Luna"
description: "Remaster truy vấn, xếp hạng, highlight và năm tạo file của SuperSearch"
---

# Kế hoạch handoff remaster tìm kiếm SuperSearch v1

## 1. Mục tiêu bàn giao

Remaster lõi tìm kiếm của SuperSearch theo bốn mục tiêu bắt buộc:

1. Mọi từ người dùng nhập đều được giữ cho đối sánh, phrase, proximity và highlight.
2. Từ phổ biến như `và` được giảm trọng số tự nhiên, không bị xóa khỏi truy vấn.
3. Desktop backend và JavaScript fallback có cùng semantics truy vấn.
4. `Năm` chỉ là năm file gốc được tạo trên hệ thống lưu trữ.

Kế hoạch này phải đủ chi tiết để model Luna triển khai độc lập, không suy đoán yêu cầu.

## 2. Quyết định nghiệp vụ đã chốt

### 2.1. Semantics tìm kiếm

- Query nhiều từ không được xóa stop-word trước khi xếp hạng.
- `và`, `của`, `nhưng`, `những`, `không`, `được` phải còn trong token hiển thị.
- `không` là token mang nghĩa phủ định, tuyệt đối không được xem là từ vô nghĩa.
- Phrase chính xác và khoảng cách từ phải có ảnh hưởng rõ ràng lên thứ hạng.
- Từ phổ biến được BM25/IDF giảm trọng số, không dùng danh sách xóa cứng.
- Query người dùng mặc định là văn bản literal, không phải cú pháp SQLite FTS5.
- `AND`, `OR`, `NOT`, dấu nháy, dấu ngoặc và dấu gạch không được gây lỗi cú pháp.
- Tìm kiếm có dấu và không dấu phải cho tập kết quả tương đương khi nghĩa từ không đổi.
- Chữ `đ` và `d` phải được chuẩn hóa nhất quán giữa index và query.

### 2.2. Semantics năm

- `year` là năm của CreationTime trên file gốc.
- Không đọc năm từ tên file.
- Không đọc năm từ nội dung.
- Không dùng năm ban hành, năm hiệu lực hoặc năm được nhắc trong tài liệu.
- Không dùng LastWriteTime làm fallback.
- Không có CreationTime đáng tin cậy thì lưu `N/A`.
- File chuyển đổi phải dùng CreationTime của file nguồn, không dùng cache Markdown.
- Thành viên trong ZIP/EPUB dùng CreationTime của file container nguồn.
- File trên network share dùng CreationTime do filesystem hoặc server trả về.
- CreationTime phản ánh lúc file được tạo trên hệ thống hiện tại.
- Sao chép sang volume khác có thể tạo CreationTime mới; UI không được tuyên bố đây là ngày tác giả soạn tài liệu.

### 2.3. Semantics xếp hạng theo thời gian

- CreationTime không tự động cộng điểm relevance.
- Xóa hoàn toàn bonus năm bắt đầu từ mốc `2010`.
- Năm chỉ dùng cho bộ lọc, thống kê và hiển thị metadata.
- Search mặc định tiếp tục ưu tiên mức liên quan nội dung.

### 2.4. Giới hạn kiến trúc

- Ứng dụng tiếp tục chạy offline hoàn toàn.
- Không thêm API, cloud service hoặc credential.
- Không thêm model embedding vào bản portable mặc định.
- Không thêm dependency nếu stdlib và SQLite FTS5 đã đáp ứng.
- Không sửa trực tiếp file trong `build_artifacts` làm source.
- Không sửa `runtime/supersearch.db` hoặc `build_artifacts/runtime/supersearch.db` bằng tay.
- Không commit, push, merge hoặc tạo backup thủ công.

## 3. Hiện trạng đã xác minh

### 3.1. Lỗi stop-word

- `data/SuperSearch.html` khai báo `STOP_WORDS` chứa `va`, `khong`, `nhung` và nhiều từ khác.
- `filterSearchWords()` xóa các token đó khi query có nhiều từ.
- Mảng đã lọc được dùng cho JavaScript scoring, snippet, title và Quick View.
- Query `và khả năng` vì thế chỉ highlight `khả năng`.
- Query `không khả năng` có nguy cơ bị rút thành `khả năng`, làm sai nghĩa.

### 3.2. Hai search engine bất nhất

- Desktop gọi `IndexStore.search_documents()` và xếp hạng bằng SQLite FTS5 BM25.
- Standalone fallback dùng scoring JavaScript tự viết.
- Desktop gửi query gốc vào FTS5 nhưng frontend lại highlight token đã lọc.
- Source authority, OCR quality, phrase bonus và year bonus chỉ tồn tại trong fallback.
- Cùng query có thể cho thứ tự khác tùy môi trường chạy.

### 3.3. Kết quả đo trên database hiện tại

- `và khả năng` trả 13 tài liệu.
- `khả năng` trả 13 tài liệu.
- `và` trả 31 tài liệu.
- BM25 contribution riêng của `và` xấp xỉ `0.000002` trên corpus mẫu.
- SQLite vẫn xét `và`, nhưng frontend làm người dùng tưởng token bị bỏ toàn bộ.

### 3.4. Lỗi query parser

- Backend đưa chuỗi người dùng trực tiếp vào toán tử `MATCH`.
- FTS5 áp dụng implicit `AND` giữa các phrase.
- Reserved words và punctuation có thể đổi nghĩa hoặc gây syntax error.
- Fallback exception hiện chuyển toàn query thành phrase literal, tạo hành vi bất ngờ.

### 3.5. Lỗi snippet và highlight

- SQLite tạo `<mark>` trong snippet.
- Frontend xóa toàn bộ `<mark>` rồi escape chuỗi.
- Backend snippet được lấy từ `content_clean`, nên có thể mất dấu tiếng Việt.
- Quick View tiếp tục dùng token đã qua stop-word filter.
- Search, snippet và highlight không dùng chung một query plan.

### 3.6. Lỗi năm

- `_detect_year()` chỉ nhận mẫu `19xx` hoặc `20xx`.
- Hàm chặn năm lớn hơn năm hiện tại cộng một.
- Hàm chỉ đọc 1.000 ký tự đầu nội dung.
- Hàm ưu tiên số năm đầu tiên trong tên file.
- Nếu không có, hàm chọn năm xuất hiện nhiều nhất trong nội dung.
- Fallback cuối dùng `os.path.getmtime()`, tức LastWriteTime.
- Database mẫu đã gán `1920` từ độ phân giải `1920 x 1080`.
- Database mẫu đã gán `2004` từ năm thành lập doanh nghiệp.
- Database mẫu đã gán `2015` từ luật tham chiếu hoặc mã sản phẩm.

### 3.7. Hạn chế công cụ impact

- GitNexus chưa index repository `SuperSearchDVC`.
- MCP hiện chỉ có repository `DEC-SYSTEM`.
- Blast radius trong kế hoạch này được truy vết trực tiếp bằng source, API và `rg`.
- Luna không được dùng kết quả GitNexus của `DEC-SYSTEM` để suy luận cho SS.

## 4. Kiến trúc đích

### 4.1. Luồng query desktop

1. Frontend gửi `activeQuery` nguyên bản và `filterQuery` riêng biệt.
2. Backend chuẩn hóa Unicode, bỏ dấu và chuyển `đ` thành `d`.
3. Backend tạo Query Plan gồm token đầy đủ, phrase và FTS expression literal.
4. SQLite FTS5 lấy candidate bằng strict query.
5. Khi strict query không có kết quả, backend chạy relaxed retrieval có kiểm soát.
6. Các ranking list phrase, NEAR, strict và relaxed được hợp nhất bằng weighted RRF.
7. Filter domain, extension và creation year được áp dụng trong SQL.
8. Backend phân trang sau khi hợp nhất thứ hạng.
9. Backend tạo plain-text snippet từ nội dung gốc có dấu.
10. Backend trả `query_tokens` cùng kết quả.
11. Frontend dùng đúng `query_tokens` để highlight title, snippet và Quick View.

### 4.2. Luồng query JavaScript fallback

1. Chuẩn hóa query theo quy tắc tương đương backend.
2. Giữ toàn bộ token cho phrase, coverage, proximity và highlight.
3. IDF tự giảm điểm token phổ biến.
4. Không xóa `và`, `không` hoặc token ngắn khỏi scoring chính.
5. Chỉ danh sách từ chất lượng thấp của spellcheck được phép bỏ token phổ biến.
6. Xóa year recency bonus.
7. Giữ tie-break deterministic hiện tại.

### 4.3. Luồng CreationTime

1. Pipeline xác định `absolute_original_path` như hiện tại.
2. Gọi `os.stat(absolute_original_path)` đúng một lần cho metadata thời gian.
3. Đọc `st_birthtime` khi thuộc tính tồn tại và lớn hơn 0.
4. Chuyển timestamp bằng local time của máy chạy SS.
5. Gán `year`, `file_year` và `file_month` từ CreationTime.
6. Nếu không có CreationTime, gán `year = "N/A"`, `file_year = 0`, `file_month = 0`.
7. Không gọi `_detect_year()`.
8. `source_mtime_ns` tiếp tục dùng LastWriteTime cho stale-check.

### 4.4. Version semantics của index

- Thêm bảng metadata nhỏ trong SQLite nếu chưa tồn tại.
- Dùng hằng `INDEX_SEMANTICS_VERSION = "2"`.
- Database cũ thiếu version được xem là cần reindex.
- `replace_entries()` ghi version trong cùng transaction sau khi rebuild FTS thành công.
- `stats()` trả `requires_reindex`.
- UI ẩn hoặc khóa bộ lọc năm khi `requires_reindex = true`.
- UI hiển thị thông báo ngắn yêu cầu quét lại.
- Không tự động xóa index cũ.
- Search nội dung vẫn hoạt động trước khi người dùng reindex.

## 5. Query Plan bắt buộc

Query Plan là dictionary nội bộ trong `src/index_store.py`, không tạo service hoặc file mới.

Các trường bắt buộc:

| Trường | Ý nghĩa |
| --- | --- |
| `raw_query` | Chuỗi người dùng nhập |
| `normalized_query` | Chuỗi ASCII lower-case dùng cho retrieval |
| `ordered_tokens` | Token theo đúng thứ tự, giữ token lặp |
| `unique_tokens` | Token duy nhất theo thứ tự xuất hiện |
| `display_tokens` | Token dùng cho highlight, không xóa stop-word |
| `informative_tokens` | Token dùng riêng cho relaxed retrieval |
| `phrase_expression` | Phrase literal đã escape |
| `near_expression` | FTS5 NEAR expression đã escape |
| `strict_expression` | Mọi token kết nối bằng explicit AND |
| `relaxed_expression` | Informative token kết nối bằng OR |

Quy tắc xây dựng:

- Chuẩn hóa bằng Unicode NFD.
- Loại combining mark.
- Chuyển `đ` và `Đ` thành `d`.
- Lower-case trước khi tokenize.
- Compound token có `.`, `_`, `/`, `-` giữ token đầy đủ và các phần hữu ích.
- Mọi token FTS phải đặt trong double quote literal.
- Double quote nội bộ phải escape theo cú pháp FTS5.
- Không nối trực tiếp raw query vào expression.
- Query chỉ có punctuation trả kết quả rỗng an toàn.
- Query một token chỉ chạy lexical BM25 literal.
- Query nhiều token luôn tạo phrase, NEAR và strict expression.
- `LOW_INFORMATION_TOKENS` chỉ được dùng cho relaxed retrieval và spellcheck.
- `LOW_INFORMATION_TOKENS` không được chứa `khong`.
- Nếu toàn query là low-information token, `informative_tokens` phải dùng toàn bộ unique token.

## 6. Thuật toán retrieval và ranking

### 6.1. Candidate retrieval

- Single-token query dùng một BM25 list.
- Multi-token query chạy strict list trước.
- Strict list bắt buộc chứa mọi ordered token bằng explicit AND.
- Phrase list bắt buộc giữ đúng token order, gồm cả `va`.
- NEAR list dùng khoảng cách tối đa tám token.
- Title phrase list chỉ xét cột `title_clean`.
- Relaxed list chỉ chạy khi strict list rỗng.
- Relaxed list dùng informative token bằng OR.
- Nếu informative token rỗng, relaxed list dùng unique token.
- Áp dụng cùng domain, extension, year và within-result filter cho mọi list.

### 6.2. BM25 trong từng list

- Giữ `bm25(documents_fts, 5.0, 1.0)`.
- Title weight là `5.0`.
- Content weight là `1.0`.
- Không thêm field mới vào FTS trong remaster này.
- Không thay tokenizer hoặc rebuild schema FTS ngoài reindex dữ liệu.

### 6.3. Weighted Reciprocal Rank Fusion

Sử dụng `k = 60` và các trọng số cố định:

| Ranking list | Trọng số |
| --- | ---: |
| Title exact phrase | 4.0 |
| Any-field exact phrase | 3.0 |
| NEAR trong tám token | 2.0 |
| Strict AND | 1.5 |
| Relaxed OR | 1.0 |
| Single-token BM25 | 1.0 |

Điểm mỗi document là tổng `weight / (60 + rank_position)` trên mọi list có document đó.

Tie-break bắt buộc theo thứ tự:

1. RRF score giảm dần.
2. Số token query được match giảm dần.
3. Exact phrase trước NEAR.
4. BM25 tốt nhất tăng dần vì SQLite dùng số âm cho kết quả tốt.
5. Title `COLLATE NOCASE` tăng dần.
6. `document_id` tăng dần.

Không được thêm heuristic authority, OCR hoặc recency trong cùng patch.

### 6.4. Candidate cap và tính minh bạch

- Mỗi ranking list có cap `2000` document ID.
- Nếu bất kỳ list nào chạm cap, response trả `truncated = true`.
- Khi `truncated = true`, UI dùng nhãn `Tìm thấy ít nhất`.
- Khi không truncated, UI dùng nhãn `Tìm thấy`.
- Không báo total tuyệt đối khi candidate đã bị cắt.
- Pagination chỉ hoạt động trong candidate set đã hợp nhất.
- Không âm thầm bỏ trạng thái truncated.

### 6.5. Within-result filter

- Frontend không nối `filterQuery` vào `activeQuery` để tạo phrase giả.
- Gửi `filterQuery` qua `filters.within_query`.
- Backend compile `within_query` thành literal AND expression riêng.
- `within_query` lọc candidate, không tham gia phrase boost của query chính.
- Query token trả về frontend gồm token chính và token filter để highlight.

## 7. Snippet và highlight

### 7.1. Backend snippet

- Không trả HTML từ backend.
- Không dùng `<mark>` do SQLite sinh làm trusted HTML.
- Snippet phải lấy từ trường `content` gốc có dấu.
- Chỉ đọc full content cho document thuộc page hiện tại.
- Không trả full content trong payload search.
- Tìm exact phrase trước.
- Nếu không có phrase, chọn cửa sổ có nhiều unique query token nhất.
- Cửa sổ mục tiêu khoảng 180 ký tự, có thể mở rộng tới ranh giới từ gần nhất.
- Prefix hoặc suffix bằng ký tự ellipsis Unicode khi bị cắt.
- Snippet trả plain text.

### 7.2. Mapping dấu và vị trí

- Helper normalization cho snippet phải trả normalized text và source offset map.
- Mỗi ký tự normalized phải trỏ về index ký tự gốc.
- Mapping phải xử lý precomposed và decomposed Vietnamese.
- Không giả định normalized text luôn có cùng chiều dài original text.
- Slice original content bằng offset map.

### 7.3. Frontend highlight

- `highlightText()` nhận plain text và `query_tokens` từ backend.
- Escape HTML trước khi chèn markup.
- Chỉ thay sentinel nội bộ thành `<mark class="highlight-mark">` sau escape.
- Sort token dài trước token ngắn để giảm nested overlap.
- Token `va` phải được highlight như mọi token khác.
- Quick View phải dùng cùng token list.
- Filter query token cũng phải được highlight.
- Không dùng backend snippet HTML.

## 8. Thiết kế CreationTime chi tiết

### 8.1. Helper backend

Tạo một helper nhỏ trong `src/app.py`, gần `_source_signature()`.

Hành vi bắt buộc:

- Nhận absolute source path.
- Gọi `os.stat()`.
- Đọc `st_birthtime` bằng `getattr`.
- Từ chối giá trị thiếu, `None`, không hữu hạn hoặc nhỏ hơn bằng 0.
- Chuyển bằng `datetime.datetime.fromtimestamp()` theo local time.
- Trả `year` và `month`; không lưu raw timestamp vì schema giữ nguyên tối thiểu.
- Mọi exception trả unknown tuple; không đoán.
- Không dùng `st_ctime` làm fallback trên Python mới.
- Không dùng `st_mtime` làm fallback.

Runtime hiện dùng Python `3.14.4` và có `st_birthtime` trên Windows.

### 8.2. Giữ schema tối thiểu

- Không đổi tên ba cột `year`, `file_year`, `file_month` trong patch này.
- `year` lưu creation year dạng text hoặc `N/A`.
- `file_year` lưu creation year dạng integer hoặc `0`.
- `file_month` lưu creation month dạng integer hoặc `0`.
- `source_mtime_ns` giữ nguyên nghĩa LastWriteTime cho cache invalidation.
- `source_sha256` giữ nguyên.
- Index `idx_documents_year` tiếp tục dùng được.

### 8.3. Deduplication

- Xóa `file_year` khỏi `entry_quality()`.
- Creation year không phải tiêu chí chất lượng tài liệu.
- Tie quality chỉ dùng `ocr_quality_score` và `wordCount`.
- Nếu hai entry cùng source identity và cùng quality, giữ entry đầu tiên deterministic.

### 8.4. UI năm

- Đổi nhãn `Năm khởi tạo` hoặc `Năm` thành `Năm tạo file` tại mọi vị trí liên quan.
- Option `Không rõ năm` đổi thành `Không rõ năm tạo`.
- Filter vẫn sinh động từ `backendStats.years`.
- Sort năm giảm dần, unknown ở cuối.
- Không hard-code danh sách năm.
- Không hard-code min/max năm.
- Không đọc năm từ query để tự bật filter.
- Xóa recency bonus hoàn toàn.

## 9. API contract sau remaster

`search_documents()` giữ positional arguments hiện tại để không phá pywebview.

Response bắt buộc bổ sung:

| Field | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `total` | integer | Số candidate duy nhất trong giới hạn |
| `page` | integer | Trang hiện tại |
| `page_size` | integer | Kích thước trang |
| `query_tokens` | array string | Token đầy đủ cho highlight |
| `truncated` | boolean | Có ranking list chạm cap hay không |
| `requires_reindex` | boolean | Index còn semantics cũ hay không |
| `documents` | array object | Kết quả đã xếp hạng và có plain snippet |

Filter input hỗ trợ:

| Field | Hành vi |
| --- | --- |
| `domain` | Equality hiện tại |
| `doc_type` | Equality hiện tại |
| `language` | Equality hiện tại |
| `extension` | Extension hiện tại |
| `year` | Creation year equality |
| `within_query` | Literal AND filter riêng |

Không xóa field response cũ trong remaster này.

## 10. File ownership

| File | Ownership | Thay đổi cho phép | Không được làm |
| --- | --- | --- | --- |
| `src/index_store.py` | Search core và SQLite | Query Plan, literal FTS, RRF, snippet, index version | Không thêm dependency, không đổi FTS schema |
| `src/app.py` | Scan metadata và pywebview API | CreationTime helper, bỏ `_detect_year`, dedup tie | Không sửa converter ngoài metadata |
| `data/SuperSearch.html` | UX search và fallback | Token semantics, highlight, year label, truncated state | Không redesign toàn giao diện |
| `tests/test_search_remaster.py` | Regression suite mới | Search, query safety, year, index version | Không dùng browser automation |
| `readme.txt` | Tài liệu text | Mô tả search và Năm tạo file | Không sửa nội dung ngoài phạm vi |
| `Readme.html` | Tài liệu HTML | Đồng bộ đúng nội dung text | Không đổi theme hoặc layout |
| `.agents/memory/project_checkpoint.yaml` | Checkpoint WSR | Ghi sau khi code hoàn tất | Không ghi trước phê duyệt |
| `.agents/memory/AG_LESSONS.jsonl` | Bài học bug | Ghi một lesson ngắn sau khi fix xác nhận | Không ghi dữ liệu người dùng |

File đầu ra chỉ tạo sau khi mọi gate nguồn đạt:

- `build_artifacts/SuperSearch.exe`
- `SuperSearch_Portable.zip`

File cấm sửa trực tiếp:

- `build_artifacts/runtime/supersearch.db`
- `runtime/supersearch.db`
- Toàn bộ `UserData/`
- Toàn bộ `src/Tesseract-OCR/`
- `requirements.txt`
- `src/SuperSearch.spec`
- `pack_portable.py`
- Hai kế hoạch cũ trong `DOCS/Planning/`

## 11. Thứ tự triển khai bắt buộc

### Gate 0 — Phê duyệt và preflight

- [ ] Đọc `AGENTS.md` và `C:\Users\DUKE NGUYEN\.codex\GEMINI.md`.
- [ ] Đọc toàn bộ file handoff này.
- [ ] Xác nhận user đã duyệt sửa code.
- [ ] Xác nhận riêng quyền chạy unittest nếu user cho phép.
- [ ] Chạy `git status --short` read-only.
- [ ] Xác nhận không có thay đổi user trùng các file ownership.
- [ ] Không tạo branch, commit, backup hoặc implementation plan.
- [ ] Không chạy GitNexus trên repository `DEC-SYSTEM` cho task này.

Gate 0 đạt khi phạm vi và quyền thực thi rõ ràng.

### Gate 1 — Neo hồi quy bằng source

- [ ] Ghi nhận logic `STOP_WORDS` và mọi call site `filterSearchWords()`.
- [ ] Ghi nhận API contract `search_documents()` hiện tại.
- [ ] Ghi nhận schema `documents` và `documents_fts` hiện tại.
- [ ] Ghi nhận `_detect_year()` và `getmtime()` hiện tại.
- [ ] Ghi nhận year bonus `detectedYear >= 2010`.
- [ ] Không thay code tại gate này.

Gate 1 đạt khi Luna có danh sách dòng tác động chính xác.

### Gate 2 — Search core backend

- [ ] Thêm normalization helper trong `src/index_store.py`.
- [ ] Thêm Query Plan đúng bảng trường tại mục 5.
- [ ] Quote mọi FTS token thành literal.
- [ ] Tách query chính và `within_query`.
- [ ] Thêm phrase, title phrase, NEAR, strict và relaxed ranking list.
- [ ] Thêm weighted RRF với đúng hằng số.
- [ ] Thêm deterministic tie-break.
- [ ] Thêm cap và `truncated`.
- [ ] Tạo plain-text snippet từ original content.
- [ ] Trả `query_tokens` trong response.
- [ ] Không trả full content từ search endpoint.
- [ ] Không nuốt schema hoặc IO error dưới fallback query.

Gate 2 đạt khi query literal không lỗi và ranking deterministic.

### Gate 3 — CreationTime backend

- [ ] Thêm helper đọc `st_birthtime` trong `src/app.py`.
- [ ] Xóa `_detect_year()` sau khi không còn caller.
- [ ] Thay block `getmtime()` bằng CreationTime helper.
- [ ] Gán `year`, `file_year`, `file_month` đúng semantics.
- [ ] Giữ `source_mtime_ns` nguyên nghĩa.
- [ ] Xóa year khỏi dedup quality.
- [ ] Không đọc filename hoặc content để gán year.

Gate 3 đạt khi `1920 x 1080`, luật `2015` và tên `2099` không ảnh hưởng year.

### Gate 4 — Index semantics version

- [ ] Tạo metadata table bằng `CREATE TABLE IF NOT EXISTS`.
- [ ] Thêm `INDEX_SEMANTICS_VERSION = "2"`.
- [ ] Ghi version sau `replace_entries()` trong cùng transaction.
- [ ] Thêm `requires_reindex` vào `stats()`.
- [ ] Thêm `requires_reindex` vào search response.
- [ ] Không xóa index cũ khi phát hiện version thiếu.
- [ ] Không tự chạy reindex khi ứng dụng khởi động.

Gate 4 đạt khi database cũ được cảnh báo nhưng search vẫn dùng được.

### Gate 5 — Frontend và fallback

- [ ] Tách `LOW_INFORMATION_TOKENS` khỏi token tìm kiếm chính.
- [ ] Đảm bảo `filterSearchWords()` không còn xóa token scoring/highlight.
- [ ] Nếu đổi tên helper, cập nhật toàn bộ call site.
- [ ] Desktop dùng `result.query_tokens` từ backend.
- [ ] `filterQuery` được gửi qua `filters.within_query`.
- [ ] Highlight title, snippet và Quick View bằng cùng token list.
- [ ] Backend snippet được coi là plain text.
- [ ] Xóa logic strip `<mark>` cũ.
- [ ] Xóa year recency bonus.
- [ ] Đổi nhãn thành `Năm tạo file`.
- [ ] Hiển thị trạng thái `truncated` đúng.
- [ ] Cảnh báo reindex khi semantics version cũ.
- [ ] Fallback JavaScript giữ toàn token và dùng IDF.
- [ ] Không thay CSS ngoài nhu cầu thông báo nhỏ.

Gate 5 đạt khi `và` xuất hiện ở mọi vùng highlight.

### Gate 6 — Regression tests

- [ ] Tạo `tests/test_search_remaster.py`.
- [ ] Dùng stdlib `unittest`, `tempfile`, `sqlite3` và `unittest.mock`.
- [ ] Không thêm test framework.
- [ ] Không dùng Chrome hoặc browser automation.
- [ ] Không phụ thuộc `UserData` thật.
- [ ] Không ghi vào runtime database thật.
- [ ] Mọi fixture dùng temporary directory.
- [ ] Chỉ chạy suite khi user đã cho phép rõ ràng.

Gate 6 đạt khi test file hoàn chỉnh và syntax hợp lệ.

### Gate 7 — Tài liệu

- [ ] Cập nhật `readme.txt`.
- [ ] Cập nhật `Readme.html` đồng bộ.
- [ ] Giải thích `Năm tạo file` là CreationTime trên filesystem hiện tại.
- [ ] Nêu rõ copy sang volume khác có thể tạo CreationTime mới.
- [ ] Nêu rõ search vẫn đọc số năm như từ khóa nội dung.
- [ ] Không tuyên bố dùng ngày ban hành hoặc metadata tác giả.

Gate 7 đạt khi tài liệu khớp hành vi thực tế.

### Gate 8 — Static verification

- [ ] Chạy `python -m py_compile src/app.py src/index_store.py tests/test_search_remaster.py`.
- [ ] Chạy `python global_tools/wsr_audit.py` theo tham số help của script.
- [ ] Xác minh không có U+FFFD hoặc mojibake.
- [ ] Chạy `rg` xác nhận `_detect_year` không còn.
- [ ] Chạy `rg` xác nhận year bonus `2010` không còn.
- [ ] Chạy `rg` xác nhận `STOP_WORDS` không còn điều khiển scoring/highlight.
- [ ] Chạy `git diff --check`.
- [ ] Chạy `git diff --stat` và kiểm tra file ngoài ownership.

Gate 8 đạt khi syntax và WSR audit PASS.

### Gate 9 — Automated verification có phê duyệt

- [ ] Chỉ chạy khi user cho phép unittest rõ ràng.
- [ ] Chạy test remaster riêng trước.
- [ ] Chạy toàn bộ unittest sau khi test riêng đạt.
- [ ] Không tự động mở browser.
- [ ] Không dùng test suite ngoài repository.

Lệnh dự kiến:

- `python -m unittest tests.test_search_remaster -v`
- `python -m unittest discover -s tests -p "test_*.py" -v`

Gate 9 đạt khi toàn bộ test được phép chạy đều PASS.

### Gate 10 — Build và portable package

- [ ] Chỉ bắt đầu sau Gate 8 và Gate 9 đạt.
- [ ] Đóng ứng dụng đang chạy nếu artifact bị lock.
- [ ] Build source bằng `src/build.py --rebuild`.
- [ ] Không sửa file build output để vá lỗi.
- [ ] Chạy `pack_portable.py` sau build thành công.
- [ ] Xác minh ZIP chứa EXE mới và external `data/SuperSearch.html` mới.
- [ ] Không nhúng thêm neural model hoặc dependency.
- [ ] Ghi kích thước EXE và ZIP vào báo cáo cuối.

Gate 10 đạt khi artifact khởi động và package đúng source đã duyệt.

### Gate 11 — Checkpoint và handback

- [ ] Ghi `.agents/memory/project_checkpoint.yaml` vì task ảnh hưởng nhiều file.
- [ ] Ghi một lesson vào `AG_LESSONS.jsonl` về stop-word và CreationTime.
- [ ] Không ghi dữ liệu tài liệu hoặc đường dẫn người dùng nhạy cảm.
- [ ] Không commit.
- [ ] Báo file đã chạm, hành vi giữ nguyên và kết quả verification.
- [ ] Đưa tối đa ba bước QA thủ công cho user.

## 12. Ma trận test bắt buộc

### 12.1. Query semantics

| ID | Dữ liệu | Query | Kết quả bắt buộc |
| --- | --- | --- | --- |
| Q01 | A chứa `và khả năng`, B chứa hai từ xa nhau | `và khả năng` | A xếp trên B |
| Q02 | A chứa `không khả năng`, B chỉ chứa `khả năng` | `không khả năng` | A xếp trên B |
| Q03 | Tài liệu chứa `điều kiện` | `điều kiện` | Tìm thấy |
| Q04 | Tài liệu chứa `điều kiện` | `dieu kien` | Tìm thấy cùng tài liệu |
| Q05 | Tài liệu chứa Unicode decomposed | Query precomposed | Tìm thấy |
| Q06 | Tài liệu chứa `AND OR NOT` literal | `AND OR NOT` | Không syntax error |
| Q07 | Tài liệu chứa dấu nháy và ngoặc | Query có dấu nháy, ngoặc | Không syntax error |
| Q08 | Query chỉ punctuation | Dấu câu | Trả rỗng an toàn |
| Q09 | Query chỉ `và của` | `và của` | Không bị rút thành query rỗng |
| Q10 | Query có compound token | `hsse-policy_v2` | Full token và part token hoạt động |
| Q11 | Query dài không có strict match | Nhiều token | Relaxed retrieval chạy có kiểm soát |
| Q12 | Cùng score | Query cố định | Thứ tự deterministic qua nhiều lần gọi |

### 12.2. API và pagination

| ID | Trường hợp | Kết quả bắt buộc |
| --- | --- | --- |
| A01 | Search desktop | Response có `query_tokens` |
| A02 | Search desktop | Response có `truncated` boolean |
| A03 | Database semantics cũ | `requires_reindex = true` |
| A04 | Sau replace entries | `requires_reindex = false` |
| A05 | `within_query` | Lọc strict nhưng không đổi phrase boost chính |
| A06 | Year filter | Chỉ lọc theo creation year |
| A07 | Page 1 và page 2 | Không trùng document ID |
| A08 | Tie score | Document order ổn định |
| A09 | Candidate cap | UI không báo total tuyệt đối |
| A10 | Search result | Không chứa full content payload |

### 12.3. CreationTime

| ID | Filename/content | Mocked timestamps | Kết quả bắt buộc |
| --- | --- | --- | --- |
| Y01 | Tên chứa `2099` | birthtime năm 2024 | Year là 2024 |
| Y02 | Nội dung chứa `1920 x 1080` | birthtime năm 2025 | Year là 2025 |
| Y03 | Nội dung nhắc luật 2015 | birthtime năm 2026 | Year là 2026 |
| Y04 | mtime năm 2030 | birthtime năm 2023 | Year là 2023 |
| Y05 | Không có `st_birthtime` | mtime hợp lệ | Year là `N/A` |
| Y06 | `st_birthtime <= 0` | mtime hợp lệ | Year là `N/A` |
| Y07 | File source không tồn tại | Không có stat | Year là `N/A` |
| Y08 | Cache Markdown mới hơn source | Source birthtime cũ | Dùng source birthtime |
| Y09 | File trong archive | Container birthtime | Dùng container birthtime |
| Y10 | Dedup cùng source | Creation year khác | Year không quyết định quality winner |

### 12.4. Snippet và highlight

| ID | Trường hợp | Kết quả bắt buộc |
| --- | --- | --- |
| H01 | `và khả năng` trong content | Cả hai cụm được highlight |
| H02 | Content có dấu | Snippet giữ dấu |
| H03 | Content decomposed | Vị trí slice không lệch |
| H04 | Content chứa HTML | HTML được escape |
| H05 | Title chứa query | Title highlight đúng |
| H06 | Quick View | Dùng cùng token list backend |
| H07 | Filter query | Token filter cũng highlight |
| H08 | Overlap token | Không tạo nested mark hỏng DOM |

### 12.5. Neo hồi quy hệ thống

| ID | Chức năng | Kết quả bắt buộc |
| --- | --- | --- |
| R01 | Scan local formats | Tổng entry đúng |
| R02 | Unsafe ZIP | Vẫn bị từ chối |
| R03 | Empty reindex | Không làm mất index cũ |
| R04 | HTML visible content | Vẫn tìm được |
| R05 | Script trong HTML | Vẫn không index |
| R06 | Extension stats | Không thay đổi semantics |
| R07 | Domain filter | Hoạt động như cũ |
| R08 | Quick View | Mở đúng tài liệu |
| R09 | Open Explorer | Không bị ảnh hưởng |
| R10 | Offline mode | Không có network call |

## 13. UAT thủ công

### UAT 1 — Stop-word và phrase

1. Quét thư mục có tài liệu chứa cụm `và khả năng`.
2. Tìm `và khả năng`.
3. Xác minh cả `và` và `khả năng` được highlight.
4. Xác minh cụm gần nhau xếp trên tài liệu có từ nằm xa nhau.

### UAT 2 — Năm tạo file

1. Mở Properties của một file nguồn trong Windows Explorer.
2. Ghi nhận trường Created.
3. Quét lại thư mục bằng SS.
4. Chọn `Năm tạo file` tương ứng.
5. Xác minh file xuất hiện đúng nhóm.
6. Xác minh năm trong nội dung không thay đổi filter.

### UAT 3 — Query an toàn

1. Tìm lần lượt `AND`, `OR`, `NOT`, dấu nháy và dấu ngoặc.
2. Xác minh không có thông báo lỗi index.
3. Tìm `điều kiện` và `dieu kien`.
4. Xác minh hai query tìm cùng tài liệu đại diện.

## 14. Tiêu chí nghiệm thu

- [ ] `và` không bị xóa khỏi Query Plan.
- [ ] `và` được highlight trong title, snippet và Quick View.
- [ ] `không` không bị xóa hoặc xem là low-information token.
- [ ] Phrase và NEAR có ảnh hưởng xác định lên thứ hạng.
- [ ] Query literal không làm lộ cú pháp FTS5.
- [ ] Desktop và fallback giữ cùng token semantics.
- [ ] Snippet backend giữ dấu và không chứa trusted HTML.
- [ ] Year chỉ đến từ `st_birthtime` của source file.
- [ ] Không còn `_detect_year()`.
- [ ] Không còn `getmtime()` dùng để gán year.
- [ ] Không còn recency bonus hard-code `2010`.
- [ ] Database cũ báo cần reindex.
- [ ] Reindex thất bại không xóa index hợp lệ.
- [ ] Không có schema migration phá dữ liệu.
- [ ] Không thêm dependency.
- [ ] Không có network call.
- [ ] Syntax audit PASS.
- [ ] WSR audit PASS.
- [ ] Automated tests PASS nếu được user cho phép chạy.
- [ ] Readme text và HTML đồng bộ.
- [ ] Build artifact chỉ sinh từ source đã qua gate.

## 15. Must remain unchanged

- Danh sách định dạng `LOCAL_CORE` hiện tại.
- Chính sách network và cloud đều disabled.
- OCR Tesseract và các giới hạn archive.
- Pipeline MarkItDown và cache stale-check.
- Bảo vệ empty reindex.
- Document identity và source path.
- Domain, extension, doc type và language filter.
- Pagination API positional arguments.
- External UI asset model.
- Theme light/dark hiện tại.
- Quick View, copy path và open Explorer.
- Build input registry trừ khi source thay đổi tự kích hoạt build.
- Portable packaging không nhúng thêm model.

## 16. Rủi ro và giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Query relaxed trả quá nhiều | Cao | Chỉ chạy khi strict rỗng, cap 2000, báo truncated |
| RRF đổi thứ tự mạnh | Cao | Test corpus cố định, tie-break deterministic |
| Highlight XSS | Cao | Backend plain text, escape trước markup |
| Sai offset Unicode | Trung bình | Normalization offset map và test decomposed |
| Database cũ còn year sai | Cao | Semantics version và cảnh báo reindex |
| CreationTime đổi khi copy file | Trung bình | Tài liệu hóa đúng nghĩa filesystem |
| Python thiếu `st_birthtime` | Thấp trên runtime hiện tại | Trả unknown, không fallback mơ hồ |
| Fallback khác backend | Trung bình | Dùng cùng token rules, test behavior đại diện |
| Search payload tăng | Trung bình | Chỉ tạo snippet cho page, không trả full content |
| Build artifact bị lock | Thấp | Dừng và yêu cầu đóng ứng dụng trước build |

Mức rủi ro tổng thể: HIGH.

Lý do: thay đổi lõi retrieval, ranking, UI highlight và semantics metadata dùng chung.

## 17. Rollback

Rollback phải dùng Git hoặc patch đảo có kiểm soát, không xóa tay file người dùng.

### 17.1. Trước build

1. Dừng triển khai ngay khi một gate thất bại.
2. Không tiếp tục sửa gate sau để che lỗi gate trước.
3. Dùng `git diff` xác định chính xác hunk của remaster.
4. Chỉ đảo các hunk thuộc file ownership.
5. Không dùng `git reset --hard` hoặc `git checkout --`.

### 17.2. Sau build nhưng chưa phát hành

1. Giữ artifact cũ bằng Git hoặc bản phát hành trước, không tạo `.bak` thủ công.
2. Không phân phối EXE hoặc ZIP mới.
3. Đảo source patch.
4. Build lại từ source đã rollback nếu user yêu cầu.

### 17.3. Sau khi user đã reindex

1. Code cũ vẫn đọc ba cột year hiện có.
2. Metadata table mới là additive và code cũ sẽ bỏ qua.
3. Nếu rollback về logic cũ, user phải reindex lại để khôi phục semantics cũ.
4. Không chỉnh sửa trực tiếp SQLite để đổi year.
5. Không đụng `UserData`.

### 17.4. Trigger rollback bắt buộc

- Query bình thường phát sinh syntax error.
- Search chậm vượt quá ba lần baseline trên corpus đại diện.
- Kết quả exact phrase xếp dưới relaxed-only result.
- Highlight tạo HTML không escape.
- Year khác Windows Created của file nguồn đại diện.
- Reindex lỗi làm mất index hợp lệ trước đó.
- Có file ngoài ownership bị sửa không giải thích được.

## 18. Nguồn kỹ thuật tham khảo

- SQLite FTS5 phrases, NEAR, BM25, highlight và snippet: https://www.sqlite.org/fts5.html
- Reciprocal Rank Fusion: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
- Python `st_birthtime`: https://docs.python.org/3/library/os.html
- Windows `FILE_BASIC_INFO.CreationTime`: https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info
- Qwen3 Embedding chỉ để đánh giá pha tương lai: https://arxiv.org/abs/2506.05176
- SPLADE v2 chỉ để đánh giá pha tương lai: https://arxiv.org/abs/2109.10086
- ColBERTv2 chỉ để đánh giá pha tương lai: https://arxiv.org/abs/2112.01488

## 19. Pha neural bị hoãn có chủ đích

Không triển khai embedding, SPLADE hoặc ColBERT trong handoff này.

Lý do:

- Portable ZIP hiện khoảng 140 MB.
- Model neural có thể lớn hơn toàn bộ ứng dụng nhiều lần.
- Cần corpus relevance có nhãn trước khi chứng minh lợi ích.
- Cần đo nDCG@10, MRR, Recall@k, latency, RAM và disk.
- Thêm neural model là thay đổi dependency và deployment riêng.

Chỉ mở pha neural bằng kế hoạch và phê duyệt khác.

## 20. Điều kiện bắt đầu thực thi

File này không cấp quyền sửa source ngay khi được tạo.

Luna chỉ được bắt đầu sau khi user gửi phê duyệt trực tiếp.

Để cho phép cả code và unittest, câu phê duyệt nên nêu rõ hai quyền này.

Không có phê duyệt unittest, Luna chỉ được viết test và chạy static verification.

## 21. Kết quả triển khai

- Đã sửa `src/index_store.py` với Query Plan literal, phrase, NEAR, weighted RRF và snippet plain-text.
- Đã giữ toàn bộ token query; `và` và `không` không còn bị xóa khỏi scoring hoặc highlight.
- Đã tách `within_query` khỏi query chính và trả `query_tokens` cho frontend.
- Đã thêm `index_metadata` với semantics version `2` và cờ `requires_reindex`.
- Đã thay suy đoán year bằng `st_birthtime` CreationTime của file nguồn.
- Đã xóa year bonus mốc `2010` và tiêu chí year khỏi dedup quality.
- Đã đổi UI thành `NĂM TẠO FILE` và khóa filter khi index cũ cần reindex.
- Đã cập nhật `readme.txt` và `Readme.html`.
- Đã thêm `tests/test_search_remaster.py` gồm 9 regression tests.
- `python -m unittest discover -s tests -p "test_*.py" -v`: 15/15 PASS.
- `python -m py_compile src/app.py src/index_store.py tests/test_search_remaster.py`: PASS.
- JavaScript syntax check bằng Node `new Function`: PASS.
- `python global_tools/wsr_audit.py`: 100/100 PASS.
- `git diff --check`: PASS.
- Đã build `build_artifacts/SuperSearch.exe` thành công.
- Đã tạo `SuperSearch_Portable.zip` thành công.
- Portable ZIP có 70 entry, không có neural model và không có duplicate path.
- Database runtime cũ chưa được tự reindex; UI sẽ yêu cầu người dùng quét lại.
