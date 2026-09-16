---
title: "Kế hoạch sửa gợi ý chính tả, xuất tài liệu và mở file gốc"
version: "v1"
status: "IMPLEMENTED"
mode: "/pl"
created: "2026-09-15"
risk_level: "MEDIUM"
description: "Khắc phục tìm kiếm sai chính tả, API xuất DOCX/Markdown, mở vị trí file gốc và ngăn đóng gói HTML mới với EXE cũ"
---

# Kế hoạch sửa gợi ý chính tả, xuất tài liệu và mở file gốc

## 1. Mục tiêu

1. Khi truy vấn không có kết quả vì sai chính tả, SuperSearch đưa ra gợi ý có căn cứ từ chính chỉ mục tài liệu, ví dụ `footbal` → `football`.
2. Nút xuất Word và Markdown hoạt động trong bản Desktop/Portable, trả lỗi rõ ràng nếu tài liệu hoặc dependency không hợp lệ.
3. Nút **Đến file gốc** mở Windows Explorer và chọn đúng file, gồm đường dẫn có khoảng trắng, đường dẫn dài và UNC.
4. Không còn trường hợp HTML mới hiển thị tính năng mà EXE cũ không có API tương ứng.

## 2. Hiện trạng đã xác minh

### 2.1. Tìm kiếm sai chính tả

- Desktop đi qua `performBackendSearch()` rồi gọi `IndexStore.search_documents()`.
- FTS5 hiện chỉ đối sánh token literal; thử nghiệm tối thiểu cho `football` trả 1 kết quả còn `footbal` trả 0.
- Nhánh Desktop luôn ẩn `spellingBanner` và không gọi logic sửa chính tả.
- Logic Levenshtein hiện chỉ chạy ở JavaScript fallback.
- `IndexStore.vocabulary()` chỉ trả `title_clean`; từ chỉ xuất hiện trong nội dung như `football` không nằm trong vocabulary autocomplete hiện tại.
- Vì vậy không nên chỉ bật lại hàm JavaScript cũ cho Desktop; spellcheck phải đọc vocabulary của toàn chỉ mục FTS.

### 2.2. Xuất DOCX/Markdown

- HTML hiện đã có hai nút và kiểm tra sự tồn tại của `window.pywebview.api.export_document`.
- `src/app.py` và `src/export_service.py` hiện có implementation xuất file trong worktree, nhưng đây là thay đổi chưa được đóng gói vào artifact hiện hành.
- `build_artifacts/SuperSearch.exe` được tạo ngày 11/09/2026, cũ hơn `app.py`, `export_service.py`, `SuperSearch.spec` và HTML ngày 12/09/2026; `needs_rebuild=True`.
- Thông báo “Chức năng xuất chưa khả dụng trong môi trường này” xuất hiện chính xác khi bridge không có `export_document`, phù hợp với trường hợp HTML mới chạy cùng EXE cũ.
- `requirements.txt` chưa khai báo trực tiếp `python-docx`, dù máy phát triển hiện có `python-docx 1.2.0` và spec đã liệt kê hidden import `docx`.
- Test cấp service hiện pass, nhưng chưa có test contract từ `Api.export_document(document_id, format)` đến file đầu ra.

### 2.3. Mở file gốc

- UI đang gửi chuỗi đường dẫn từ document sang `open_explorer(path)`.
- Backend có `resolve_file_path()` và bản vá bỏ tiền tố long-path, nhưng artifact hiện hành cũ hơn bản vá này.
- Contract boolean hiện tại không cho UI biết rõ “đã chọn file”, “chỉ mở được thư mục cha” hay “không tồn tại”.
- Chuỗi xử lý tiền tố cần bao phủ riêng `\\?\C:\...` và `\\?\UNC\server\share\...`; test hiện chỉ bao phủ long path dạng ổ đĩa.
- Luồng đáng tin cậy hơn là gửi `document_id`, để backend tự lấy `absolute_original_path` trong SQLite thay vì tin vào path do UI truyền lại.

### 2.4. Lỗi quy trình phát hành

- `data/SuperSearch.html` là tài nguyên ngoài EXE và được nạp trực tiếp khi chạy.
- `pack_portable.py` chép EXE hiện có và HTML hiện có vào cùng ZIP nhưng chưa từ chối EXE đã cũ so với input backend.
- Đây là nguyên nhân hệ thống cho phép giao diện và API bridge lệch phiên bản.

## 3. Quyết định hành vi

- Chỉ chạy spellcheck khi truy vấn gốc trả 0 kết quả; không tăng chi phí cho truy vấn thành công.
- Không tự ý thay query. UI hiển thị: `Không tìm thấy kết quả cho footbal. Có phải ý bạn là: football?`; người dùng bấm vào gợi ý để tìm lại.
- Chỉ gợi ý từ có trong FTS vocabulary và chỉ hiển thị nếu truy vấn đã sửa thật sự trả kết quả dưới cùng bộ lọc hiện tại.
- Không sửa token ngắn tối đa 3 ký tự, mã có số/ký tự đường dẫn, hoặc token được bảo vệ.
- Với query nhiều từ, giữ nguyên các token đúng và chỉ thay token sai.
- Autocomplete tiêu đề và spellcheck nội dung là hai chức năng khác nhau; không đẩy toàn vocabulary nội dung sang JavaScript.
- Export mặc định vào `runtime/exports`; tên file được làm sạch, không ghi đè file có sẵn và trả về đường dẫn tuyệt đối.
- Backend trả object có cấu trúc cho thao tác mở file, thay vì chỉ trả boolean.
- Không yêu cầu quét lại chỉ để có spellcheck: vocabulary phải đọc từ FTS5 hiện có.

## 4. Thiết kế API đích

### 4.1. Search response

Giữ nguyên các field hiện tại và thêm:

```json
{
  "original_query": "footbal",
  "suggested_query": "football",
  "suggestion_reason": "spelling"
}
```

`suggested_query` và `suggestion_reason` là `null` khi không có gợi ý đạt ngưỡng hoặc query gốc đã có kết quả.

### 4.2. Mở file theo document ID

Thêm API:

```text
open_document_location(document_id) -> {
  success: bool,
  action: "selected_file" | "opened_parent" | "not_found" | "error",
  path: string,
  error?: string
}
```

Giữ `open_explorer(path)` làm wrapper tương thích cho call site cũ, nhưng Quick View và kết quả tìm kiếm chuyển sang API theo `document_id`.

### 4.3. Capability/version handshake

Thêm API nhẹ:

```text
get_runtime_capabilities() -> {
  api_version: integer,
  export_document: bool,
  open_document_location: bool,
  spelling_suggestion: bool
}
```

UI chỉ bật nút sau `pywebviewready`; nếu EXE cũ, hiển thị thông báo “Cần cập nhật SuperSearch.exe” thay vì thông báo chung “không khả dụng”.

## 5. Các bước triển khai

### Gate 1 — Baseline và bảo toàn worktree

- Ghi nhận toàn bộ file đang modified/untracked; không reset hoặc ghi đè thay đổi đang làm dở.
- Chốt test fixture nhỏ có từ `football` chỉ trong body, không có trong title.
- Chạy lại các suite search/export/path hiện có để có baseline.

Gate đạt khi có thể tái hiện `football=1`, `footbal=0` và xác nhận EXE hiện tại stale.

### Gate 2 — Spellcheck tại backend

- Trong `src/index_store.py`, tạo lớp truy vấn vocabulary dựa trên `fts5vocab(documents_fts, 'row')` hoặc virtual table tương đương.
- Lấy candidate theo độ dài ±2, ưu tiên cùng ký tự đầu/prefix và giới hạn số candidate để tránh quét vocabulary không giới hạn.
- Cài edit distance deterministic bằng stdlib; ngưỡng dự kiến: tối đa 1 edit cho từ dài 4–5, tối đa 2 edit cho từ dài từ 6 trở lên.
- Tie-break theo khoảng cách edit, độ tương đồng chuẩn hóa, document frequency rồi thứ tự chữ cái để kết quả ổn định.
- Tách search core không kèm suggestion khỏi wrapper public để có thể kiểm chứng query gợi ý mà không đệ quy.
- Chỉ gắn `suggested_query` nếu query gợi ý có ít nhất một kết quả với cùng domain/extension/year/within-query.
- Không thay schema `documents`; không tăng `INDEX_SEMANTICS_VERSION` nếu chỉ thêm `fts5vocab` và không cần reindex.

Gate đạt khi `footbal` trả 0 document nhưng có `suggested_query=football`, còn `football` trả kết quả và không có suggestion.

### Gate 3 — UX gợi ý thống nhất

- Cập nhật `performBackendSearch()` trong `data/SuperSearch.html` để render `spellingBanner` từ response backend.
- Bấm gợi ý đi qua `searchSuggestionDirect()` và thực hiện query mới bình thường.
- Không thay nội dung input, highlight hoặc thống kê trước khi người dùng bấm.
- Điều chỉnh nhánh JavaScript fallback về cùng hành vi “gợi ý để bấm”, tránh Desktop tự đề xuất còn standalone tự thay query.
- Giữ escape bằng DOM node/textContent hiện tại; không chèn query/suggestion bằng `innerHTML`.

Gate đạt khi cả Desktop và fallback hiển thị cùng một thông điệp và không tự đổi query.

### Gate 4 — Hoàn thiện export end-to-end

- Giữ `src/export_service.py` là nơi duy nhất tạo Markdown/DOCX; `Api.export_document()` chỉ validate, chọn tên/path và ánh xạ lỗi.
- Thêm `python-docx==1.2.0` vào `requirements.txt` và giữ hidden import/data cần thiết trong `src/SuperSearch.spec`.
- Validate `document_id`, format allowlist và nội dung tài liệu trước khi ghi.
- Làm sạch tên file, có fallback khi title rỗng và tránh collision trong cùng giây.
- Ghi file tạm trong chính thư mục đích rồi `os.replace` để không để lại file DOCX/Markdown hỏng khi export thất bại.
- UI khóa nút trong lúc export, mở lại trong `finally`, và hiển thị error backend nguyên nhân cụ thể.

Gate đạt khi gọi API bằng document ID tạo được cả `.md` và `.docx` hợp lệ trong `runtime/exports`.

### Gate 5 — Sửa mở file gốc

- Thêm `open_document_location(document_id)` vào `src/app.py`.
- Lấy document từ SQLite, ưu tiên `absolute_original_path`, rồi resolve qua `IndexStore.resolve_file_path()`.
- Tách helper chuẩn hóa path dành cho filesystem và path dành cho Explorer.
- Xử lý đúng local path, khoảng trắng, `\\?\C:\...`, `\\?\UNC\...` và UNC chuẩn `\\server\share\...`.
- Gọi `subprocess.Popen()` bằng danh sách đối số, không qua shell.
- Nếu file tồn tại: dùng `/select,<path>`; nếu Explorer không thể chọn nhưng thư mục cha tồn tại: mở thư mục cha và trả `opened_parent`; nếu không còn file: trả `not_found`.
- UI chỉ báo “đang chọn file” khi action là `selected_file`; fallback clipboard phải báo đúng việc đã/không sao chép.

Gate đạt khi mock command chính xác cho mọi biến thể path và Portable thật mở đúng file mẫu.

### Gate 6 — Đồng bộ bridge và chặn artifact stale

- UI đọc `get_runtime_capabilities()` sau `pywebviewready` rồi mới enable Export/Open Original.
- Dùng capability để phân biệt chạy browser standalone với chạy EXE cũ.
- Trong `pack_portable.py`, tái sử dụng freshness check của build hoặc helper dùng chung; từ chối đóng gói nếu bất kỳ backend input nào mới hơn `build_artifacts/SuperSearch.exe`.
- Đảm bảo danh sách build input chứa `export_service.py`, spec và `requirements.txt`.
- Build bắt buộc trước package khi API backend thay đổi.
- Sau build, tạo ZIP mới và xác minh manifest chứa EXE mới, HTML mới, KaTeX assets và Tesseract runtime.

Gate đạt khi không thể tạo ZIP từ EXE cũ hơn source và capability của HTML khớp EXE mới.

## 6. Test plan

### 6.1. Unit/backend

- `football` có kết quả; `footbal` gợi ý `football`.
- Từ chuẩn đã có kết quả không sinh suggestion.
- Candidate xuất hiện chỉ trong body vẫn được gợi ý.
- Candidate ở title/heading/content đều được xét.
- Query nhiều từ chỉ sửa token sai.
- Không sửa mã như `ISO9001`, `A-01`, đường dẫn hoặc token ≤3 ký tự.
- Không gợi ý candidate không có kết quả sau khi áp dụng filter.
- Tie-break ổn định khi có nhiều candidate cùng edit distance.
- Unicode/không dấu và `đ`/`d` không làm hỏng query hiện tại.

### 6.2. Export

- API export Markdown bằng document ID, kiểm tra UTF-8 và nội dung.
- API export DOCX, mở lại bằng `python-docx` và kiểm tra cấu trúc tối thiểu.
- Document ID không tồn tại, format không hỗ trợ, title rỗng và output collision.
- Mô phỏng thiếu `python-docx` trả error rõ ràng, không để file rác.

### 6.3. File gốc

- Path local thường, path có khoảng trắng, long drive path, long UNC path và UNC thường.
- File không tồn tại nhưng thư mục cha còn tồn tại.
- Document ID không tồn tại và record có path rỗng.
- Kiểm tra không dùng `shell=True` và không làm sai dấu phẩy/khoảng trắng trong `/select,`.

### 6.4. Bridge/build/portable

- HTML nhận capability sau `pywebviewready` và enable đúng ba tính năng.
- EXE cũ cho thông báo cần cập nhật, không giả vờ export/open thành công.
- `pack_portable.py` fail khi EXE stale và pass sau rebuild.
- Smoke test trên bản Portable mới: scan fixture → `footbal` thấy gợi ý → mở Quick View → xuất MD/DOCX → mở file gốc.

## 7. Lệnh xác minh dự kiến

```powershell
python -m py_compile src/app.py src/index_store.py src/export_service.py
python -m unittest tests.test_search_remaster -v
python -m unittest tests.test_advanced_capabilities tests.test_audit_phase3_fixes tests.test_d_ocr_features -v
python -m unittest discover -s tests -v
python src/build.py --rebuild
python pack_portable.py
```

Sau đó chạy smoke test thủ công trên `build_artifacts/SuperSearch.exe` và một bản giải nén mới của `SuperSearch_Portable.zip`.

## 8. Tiêu chí nghiệm thu

- Query `footbal` không có kết quả gốc nhưng hiển thị link `football`; bấm link trả đúng tài liệu.
- Không phát sinh gợi ý sai khi query gốc đã có kết quả.
- Xuất Markdown và DOCX thành công từ Quick View trong bản Portable mới.
- File DOCX mở được bằng Word; Markdown đọc đúng UTF-8.
- **Đến file gốc** chọn đúng file trên local, path dài và UNC; trường hợp không tồn tại báo đúng trạng thái.
- UI không bật tính năng nếu backend không khai báo capability.
- Packaging từ chối EXE stale.
- Toàn bộ test suite pass, build mới hơn mọi input backend và ZIP chứa đúng artifact mới.

## 9. Phạm vi file dự kiến

| File | Thay đổi |
|---|---|
| `src/index_store.py` | FTS vocabulary, edit-distance suggestion, search response |
| `src/app.py` | Export contract, open theo document ID, capabilities |
| `src/export_service.py` | Ghi atomic, filename/output hardening |
| `data/SuperSearch.html` | Banner suggestion, trạng thái nút, capability handshake |
| `src/SuperSearch.spec` | Dependency đóng gói DOCX |
| `requirements.txt` | Pin `python-docx` |
| `src/build.py` / `pack_portable.py` | Freshness gate dùng chung |
| `tests/test_search_remaster.py` | Regression spellcheck backend |
| Test export/path hiện có hoặc test integration mới | API, path variants, stale packaging |

## 10. Rủi ro và kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| Spellcheck chậm trên vocabulary lớn | Chỉ chạy khi 0 kết quả, candidate có giới hạn, truy vấn FTS vocab theo prefix/độ dài |
| Gợi ý từ hiếm hoặc sai ngữ cảnh | Ngưỡng edit chặt, ưu tiên document frequency, xác minh query sửa có kết quả |
| Recursion khi xác minh suggestion | Tách search core và wrapper suggestion |
| Export hoạt động trên máy dev nhưng thiếu trong EXE | Dependency explicit, spec, API test và smoke test artifact |
| Explorer xử lý long UNC khác local path | Helper riêng và test riêng từng prefix |
| HTML/EXE tiếp tục lệch phiên bản | Capability handshake cộng packaging freshness gate |
| Xung đột với worktree đang sửa dở | Chỉ chỉnh đúng file/call site đã liệt kê, không reset thay đổi hiện có |

## 11. Implementation record

- Backend spellcheck đã triển khai bằng FTS5 vocabulary và Levenshtein có giới hạn; `footbal` trả `suggested_query=football` mà không tự đổi query.
- UI Desktop đã render banner gợi ý, capability handshake sau `pywebviewready`, mở file theo `document_id` và báo lỗi cập nhật EXE rõ ràng.
- Export API đã ghi file qua temporary path rồi `os.replace`; `python-docx==1.2.0` đã được khai báo.
- `pack_portable.py` đã từ chối EXE stale trước khi tạo ZIP.
- `python -m unittest discover -s tests -v`: 74 tests pass.
- `python src/build.py --rebuild`: pass; `build_artifacts/SuperSearch.exe` tạo ngày 15/09/2026.
- `python pack_portable.py`: pass; `SuperSearch_Portable.zip` tạo ngày 15/09/2026.
- UAT follow-up: success dialog hiện đầy đủ filename/path và nút đi tới file xuất; result list/preview mở file theo `document_id`.
- UAT follow-up: full scan ưu tiên `scan_target` khi khôi phục đường dẫn nguồn, tránh trỏ nhầm về thư mục chứa EXE (ví dụ My Documents).
- UAT follow-up 2: legacy result không có `document_id` nay được `open_explorer()` resolve đường dẫn tương đối theo `scan_dir` trước khi dùng working directory, tránh mọi nút rơi về My Documents.
- UAT follow-up 3: tách `/select,` và file path thành hai argv riêng để Explorer không cắt sai tên file có dấu phẩy rồi fallback về My Documents.
