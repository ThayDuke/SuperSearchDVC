---
mode: self-execution
version: "v1"
status: IMPLEMENTED_PENDING_MANUAL_QA
risk_level: MEDIUM
failure_layer: UI/Logic
baseline_ref: cdc8a1d
current_step: P6
last_verified: 2026-09-02
source_of_truth: data/SuperSearch.html
---
# Kế hoạch xử lý scrollbar highlight v1
## Mục tiêu và giới hạn
- Chỉ tạo marker cho vùng khớp đủ mạnh với toàn bộ truy vấn.
- Giảm marker trùng, chồng và nhiễu trên tài liệu dài.
- Giữ inline highlight của mọi token để không tái phát lỗi bỏ từ “và”.
- Giữ nguyên tìm kiếm, BM25/RRF, snippet, Quick View, theme, API và schema.
## Definition of Done
- Multi-token không tạo marker từ token rời; single-token tối đa một marker mỗi block.
## Verified Baseline
- `filterSearchWords()` giữ toàn bộ token tại `data/SuperSearch.html:2282`.
- Quick View tạo inline mark tại `data/SuperSearch.html:4327`.
- Scrollbar lấy mọi raw mark; giới hạn 150 chỉ lấy mẫu, không đánh giá coverage/proximity.
## Impact Map
| File | Loại | Tác động |
|---|---|---|
| `data/SuperSearch.html` | MODIFY | Tách inline mark khỏi marker relevance |
| `DOCS/Planning/planning_scrollbar_highlight_relevance.md` | MODIFY | Ghi checkpoint thực thi |
| `build_artifacts/SuperSearch.exe` | GENERATED | Rebuild sau khi audit đạt |
| `SuperSearch_Portable.zip` | GENERATED | Đóng gói sau khi build đạt |
## Change Contract
- Must remain unchanged: mọi token vẫn được highlight trong nội dung Quick View.
- Must remain unchanged: title, snippet, ranking và số kết quả.
- Must remain unchanged: accent-insensitive, ranh giới nguyên token và tiếng Việt.
- Must remain unchanged: click, smooth scroll, modal và hai theme hiện hữu.
## Thuật toán marker relevance
- Nhóm inline marks theo block nội dung gần nhất, ưu tiên `p`.
- Exact phrase trong block luôn đạt mức tin cậy cao nhất.
- Query 2–3 token: yêu cầu đủ mọi token trong cửa sổ 160 ký tự.
- Query từ 4 token: yêu cầu 60%, tối thiểu ba token; single-token lấy một target mỗi block.
- So khớp nguyên token; score theo exact phrase, full coverage, coverage ngưỡng.
- Mỗi bucket 8px giữ target mạnh nhất; tối đa 60 marker theo chiều dọc.
- Không có target đủ chuẩn: không tự cuộn, inline highlight vẫn hiển thị.
## Atomic Execution Steps
- [x] P1: Chốt bốn kịch bản query 1, 2, 3 và 5 token.
- [x] P2: Thêm helper coverage, proximity, gom block và score cục bộ.
- [x] P3: Thay raw marks bằng target đã bucket 8px, giới hạn 60.
- [x] P4: Chuyển auto-scroll sang target đạt chuẩn đầu tiên.
- [x] P5: Kiểm tra syntax JavaScript và chạy WSR static audit.
- [ ] P6: QA thủ công tối đa ba kịch bản trong cả hai theme.
- [x] P7: Rebuild, đóng gói, ghi SHA256 và checkpoint IMPLEMENTED.
## Acceptance Matrix
| ID | Criterion | Evidence |
|---|---|---|
| A1 | `và khả năng` không marker nơi chỉ có `và` | QA fixture |
| A2 | `khả năng` yêu cầu cả hai token gần nhau | QA fixture |
| A3 | Query một token không tạo marker chồng | Quan sát track |
| A4 | Inline highlight vẫn giữ mọi token | So sánh Quick View |
| A5 | Marker click tới đúng block | QA click |
| A6 | Hai theme sạch; không lỗi syntax/mojibake | QA, WSR PASS |
## Stop Conditions và Rollback
- Dừng nếu cần sửa `src/index_store.py` hoặc thay đổi API tìm kiếm.
- Dừng nếu mất inline highlight hoặc marker sai sau khi modal hoàn tất layout.
- Rollback riêng marker/helper; giữ toàn bộ thay đổi remaster đang có.
## Resume Checkpoint
- Completed: audit source, xác định nguyên nhân, chốt thuật toán.
- Current: P6; files touched: plan và `data/SuperSearch.html`; evidence: syntax, WSR 100/100, build/package PASS.
- Next: người dùng QA ba kịch bản Quick View trong hai theme.
- Blocker: không có; UI automation không dùng.
- Blocker: không có.
