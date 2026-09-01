---
title: "Kế hoạch mở rộng đầy đủ MarkItDown v1"
version: v1
status: PLAN_DRAFT
workflow: /pl
created: 2026-09-01
markitdown_current: 0.1.6
markitdown_target: 0.1.7
feasibility: FEASIBLE_WITH_PROFILES
---

# Kế hoạch mở rộng đầy đủ MarkItDown v1

## 1. Kết luận khả thi

Khả thi nếu hiểu “đầy đủ” theo mô hình capability profile.

Không nên nhúng `markitdown[all]`, cloud SDK, LLM và media engine vào EXE mặc định.
Việc này đi ngược mục tiêu EXE nhỏ, build nhanh và ứng dụng offline.

Thiết kế đề xuất:

- `LOCAL_CORE`: bật mặc định, chỉ đọc file cục bộ, không mạng, không API key.
- `NETWORK_OPTIONAL`: audio transcription và URL, tắt mặc định, người dùng chủ động bật.
- `CLOUD_OPTIONAL`: Azure và LLM/plugin, tắt mặc định, yêu cầu cấu hình và cảnh báo chi phí.
- Mỗi capability có trạng thái `available`, `missing_dependency`, `disabled` hoặc `failed`.

## 2. Hiện trạng xác minh

- SuperSearch đang pin MarkItDown `0.1.6`.
- Bản mới nhất trên PyPI ngày 2026-07-29 là `0.1.7`.
- `0.1.7` chủ yếu sửa PPTX, SVG và công thức; nâng cấp có rủi ro thấp.
- EXE hiện loại `pydub`, `speech_recognition`, `azure`, `openai` và `markitdown_ocr`.
- Scanner hiện chỉ cho PDF, Office, ảnh JPEG/PNG, DOC/XLS cũ và HTML/HTM.
- Converter CSV, text, JSON, ZIP, EPUB, IPYNB, MSG và RSS đã nằm trong MarkItDown.
- GitNexus chưa index repo này; phân tích tác động dùng source, dependency và build spec trực tiếp.

Nguồn chính thức:

- https://github.com/microsoft/markitdown/blob/main/README.md
- https://github.com/microsoft/markitdown/releases/tag/v0.1.7
- https://pypi.org/project/markitdown/

## 3. Ma trận định dạng đề xuất

| Nhóm | Định dạng | Trạng thái đề xuất | Ghi chú |
| --- | --- | --- | --- |
| Đã có | PDF, DOC, DOCX, XLS, XLSX, PPTX | Giữ bật | Giữ OCR PDF và converter legacy hiện tại |
| Đã có | PNG, JPG, JPEG | Giữ bật | OCR Tesseract cục bộ |
| Đã có | HTML, HTM, MD | Giữ bật | Đã kiểm thử |
| Text | TXT, TEXT, MARKDOWN | Bật `LOCAL_CORE` | Index văn bản thuần |
| Dữ liệu | JSON, JSONL, CSV | Bật `LOCAL_CORE` | CSV thành bảng Markdown |
| Feed/XML | XML, RSS, ATOM | Bật `LOCAL_CORE` | RSS/Atom có cấu trúc; XML thường là text |
| Tài liệu | EPUB, IPYNB, MSG | Bật `LOCAL_CORE` | MSG cần `olefile`; IPYNB giữ code cell |
| Archive | ZIP | Bật có giới hạn | Một tài liệu index, giữ heading đường dẫn file con |
| Ảnh mở rộng | BMP, TIF, TIFF | Bật qua OCR cục bộ | Mở rộng converter Pillow/Tesseract hiện có |
| Media | WAV, MP3, M4A, MP4 | `NETWORK_OPTIONAL` | MarkItDown dùng SpeechRecognition/Google; MP3/MP4 cần FFmpeg |
| URL | YouTube, Wikipedia, Bing | `NETWORK_OPTIONAL` | Cần luồng “Thêm URL”; không thuộc quét thư mục |
| Cloud | Azure Document Intelligence | `CLOUD_OPTIONAL` | Có mạng, credential và chi phí |
| Cloud | Azure Content Understanding | `CLOUD_OPTIONAL` | Hỗ trợ thêm RTF, EML, ảnh, audio, video |
| LLM | Mô tả ảnh, OCR embedded image | `CLOUD_OPTIONAL` | Plugin OCR cần LLM client/model |
| Plugin khác | Plugin bên thứ ba | Không bật tự động | Chỉ dùng allowlist đã audit |

Không tuyên bố hỗ trợ local-native cho EML, RTF, video và mọi ảnh RAW.
Các dạng này chỉ khả dụng qua cloud/plugin phù hợp.

## 4. Phạm vi triển khai được khuyến nghị

### Pha A — Hoàn tất `LOCAL_CORE`

- Nâng MarkItDown từ `0.1.6` lên `0.1.7`.
- Pin trực tiếp dependency đang dùng nhưng chưa có trong `requirements.txt`, gồm `mammoth` và `lxml`.
- Gom allowlist định dạng thành một registry duy nhất trong backend.
- Thêm TXT, TEXT, MARKDOWN, JSON, JSONL, CSV, XML, RSS, ATOM, EPUB, IPYNB, MSG và ZIP.
- Mở rộng OCR ảnh cho BMP, TIF và TIFF.
- Thay `convert()` bằng `convert_local()` để chặn URL ngoài ý muốn.
- Giữ converter PDF, ảnh, DOC và XLS tùy chỉnh ở độ ưu tiên hiện tại.
- Không thay schema SQLite; thống kê extension và bộ lọc tiếp tục sinh động.

### Pha B — An toàn và kiểm soát tài nguyên

- Bọc ZIP bằng giới hạn số entry, tổng byte giải nén, compression ratio và độ sâu lồng.
- Từ chối file quá lớn theo từng nhóm định dạng trước khi đưa vào worker.
- Ghi lỗi theo file nhưng không xóa index hợp lệ trước đó.
- Phân biệt `unsupported`, `missing_dependency`, `too_large`, `unsafe_archive` và `conversion_failed`.
- Không index nội dung lỗi như một tài liệu hợp lệ.
- Giữ scan incremental theo size, mtime và SHA-256 hiện tại.

### Pha C — UX và khả năng quan sát

- Hiển thị danh sách định dạng thực sự khả dụng từ backend.
- Hiển thị dependency thiếu thay vì báo hỗ trợ chung chung.
- Bổ sung thống kê lỗi theo định dạng sau scan.
- Quick View tiếp tục đọc Markdown cache; không cần renderer riêng.
- Cập nhật `readme.txt` và `Readme.html` với giới hạn local, network và cloud.

### Pha D — Capability tùy chọn

- Tạo dependency pack ngoài EXE cho audio/URL/cloud.
- Giữ các module này ngoài `SuperSearch.exe` để không tăng kích thước và thời gian build mặc định.
- Chỉ bật network sau xác nhận rõ của người dùng trong Settings.
- Lưu credential bằng cơ chế Windows an toàn; không ghi khóa vào config hoặc log.
- Không bật plugin bên thứ ba theo cơ chế discovery tự động.

Pha D là tùy chọn riêng, cần phê duyệt bổ sung trước khi triển khai.

## 5. Tác động dự kiến

| Thành phần | Tác động | Rủi ro |
| --- | --- | --- |
| `src/app.py` | Registry, allowlist, `convert_local`, OCR ảnh mở rộng, lỗi chi tiết | Trung bình |
| `requirements.txt` | Nâng MarkItDown, pin dependency tái lập build | Thấp |
| `src/SuperSearch.spec` | Giữ cloud/audio ngoài EXE; xác minh hidden imports local | Trung bình |
| `src/build.py` | Theo dõi dependency/registry trong incremental build | Thấp |
| `src/index_store.py` | Không đổi schema; xác minh extension filter | Thấp |
| `data/SuperSearch.html` | Danh sách capability và lỗi scan | Thấp |
| `pack_portable.py` | Chỉ đổi khi có dependency pack tùy chọn | Thấp |
| Tests | Thêm fixture cho từng converter và archive nguy hiểm | Trung bình |

Blast radius chính nằm trong pipeline `scan_and_index`.
Search FTS5, cache metadata và API tài liệu không cần thay đổi giao thức.

Mức rủi ro tổng thể: TRUNG BÌNH.

## 6. Gate triển khai

### Gate 1 — Dependency và baseline

- Chụp kích thước EXE, thời gian clean build và incremental build hiện tại.
- Nâng `0.1.7`, chạy test hiện có trước khi thêm extension.
- `pip check` đạt và build từ môi trường sạch có thể tái lập.

### Gate 2 — Text và structured files

- Bật TXT, JSON, JSONL, CSV, XML, RSS và ATOM.
- Xác minh Unicode tiếng Việt, encoding legacy và dữ liệu rỗng.
- Script hoặc nội dung lỗi không làm mất index cũ.

### Gate 3 — EPUB, IPYNB, MSG và ảnh mở rộng

- Index được heading, body, code cell, metadata email và OCR ảnh.
- File thiếu dependency trả lỗi capability rõ.
- Không có record rỗng hoặc record chứa chuỗi lỗi converter.

### Gate 4 — ZIP an toàn

- ZIP thường và ZIP lồng hoạt động trong giới hạn.
- ZIP bomb, quá nhiều entry, path bất thường hoặc encrypted ZIP bị từ chối.
- Không ghi file giải nén vào thư mục nguồn.

### Gate 5 — Build và đóng gói

- Test toàn bộ đạt.
- EXE `LOCAL_CORE` tăng không quá 5 MiB so với baseline 76.31 MiB.
- Build lặp không đổi đầu vào vẫn bỏ qua nhanh.
- Portable ZIP chứa đúng EXE và runtime ngoài.
- Không vô tình nhúng Azure, OpenAI, SpeechRecognition hoặc FFmpeg.

## 7. Ma trận kiểm thử tối thiểu

| Fixture | Kiểm tra |
| --- | --- |
| TXT/TEXT/MARKDOWN | Unicode, dòng, tiêu đề tìm được |
| JSON/JSONL | Nội dung chuỗi và số tìm được |
| CSV | Header, ô, dấu phẩy và Unicode |
| XML | Văn bản thường không bị loại |
| RSS/ATOM | Title và entry được index |
| EPUB | Chương và metadata tìm được |
| IPYNB | Markdown cell và code cell tìm được |
| MSG | Subject, sender, body và attachment hỗ trợ |
| BMP/TIF/TIFF | OCR Việt/Anh tìm được |
| ZIP | File con hỗ trợ được gộp, file lạ bị bỏ qua |
| ZIP nguy hiểm | Bị chặn, index cũ được giữ |
| Quét lại | Không trùng record, cache đúng |
| Build artifact path | Không bị lọc nhầm |

## 8. Tiêu chí hoàn tất

- Toàn bộ converter local khả thi của MarkItDown được SuperSearch phát hiện và index.
- Không mở quyền mạng trong luồng quét thư mục.
- Định dạng cloud/network được mô tả đúng, không giả vờ offline.
- Dependency thiếu có thông báo rõ, không tạo tài liệu rỗng.
- ZIP và file lớn có giới hạn an toàn.
- EXE mặc định vẫn nhỏ và incremental build vẫn nhanh.
- Test, build, portable packaging và tài liệu đều đạt.

## 9. Rollback

- Trả registry về allowlist trước đó.
- Pin lại MarkItDown `0.1.6` nếu `0.1.7` gây regression.
- Tắt extension mới bằng capability flag, không đổi schema.
- Quét lại nguồn để dọn cache mồ côi sau một lần commit index thành công.

## 10. Điều kiện triển khai

Kế hoạch này không cấp quyền sửa source.

Một tín hiệu phê duyệt mới sẽ áp dụng Pha A, B và C.
Pha D cần một quyết định riêng vì phát sinh mạng, credential và chi phí.

## 11. Kết quả triển khai sau phê duyệt

- Đã hoàn tất Pha A, B và C với profile `LOCAL_CORE` gồm 28 extension.
- Đã nâng MarkItDown lên `0.1.7` và pin `mammoth`, `lxml` cho build tái lập.
- Đã dùng `convert_local()` cho mọi file ngoài ZIP.
- Đã thêm giới hạn file và ZIP, gồm entry, tổng byte, compression ratio, mã hóa và độ sâu.
- Đã thêm capability API, danh sách định dạng trong UI và error summary sau scan.
- Đã kiểm thử TXT, TEXT, MARKDOWN, JSON, JSONL, CSV, XML, RSS, ATOM, IPYNB, EPUB và ZIP.
- 6/6 regression test đạt; ZIP nguy hiểm bị chặn và index hợp lệ được giữ.
- EXE mới có 80.017.284 byte, chỉ tăng 3.951 byte so với baseline.
- Incremental build không đổi đầu vào được bỏ qua trong khoảng 52 ms.
- Archive không chứa Azure, OpenAI, SpeechRecognition, pydub hoặc `markitdown_ocr`.
- Pha D chưa triển khai, đúng phạm vi phê duyệt.
