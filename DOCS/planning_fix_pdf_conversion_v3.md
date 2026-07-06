---
task_name: "Tối ưu hóa tốc độ dừng và tạm dừng tiến trình quét tài liệu"
date: "2026-07-03"
version: "v3"
status: "Draft"
target_files:
  - "d:/CICT BACKUP\CICT PROCEDURES/MDBANK/src/app.py"
---

# Lập kế hoạch tối ưu tốc độ Pause và Abort

> [!TIP]
> ### [HIỂU_YÊU_CẦU] (Confidence Score: 10/10)
> 1. **Hiện tượng:** Khi bấm Pause hoặc Abort, app phản hồi rất chậm. Người dùng phải đợi các file PDF lớn chạy xong hoàn toàn (mất 5-30 giây) thì tiến trình mới thực sự dừng/hủy.
> 2. **Nguyên nhân:**
>    - Các luồng phụ đang chạy OCR qua vòng lặp nhiều trang của PDF không thể bị ngắt giữa chừng.
>    - Tiến trình chính bị block ở `self.executor.shutdown(wait=True)` trong khối `finally` của `scan_and_index()`, bắt buộc phải đợi tất cả các task chạy dở kết thúc.
> 3. **Mục tiêu:**
>    - Ngắt hoặc tạm dừng việc xử lý trang PDF ngay lập tức (giữa các trang) khi bấm Pause/Abort.
>    - Giải phóng block luồng chính ngay lập tức khi bấm Abort bằng cách tắt executor không chờ đợi (`wait=False`).

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Bảo toàn logic convert PDF sang text và OCR Tesseract.
- Giữ nguyên các cơ chế an toàn lưu DB và SSFolder.

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> 1. **Cải tiến constructor của Custom Converters:**
>    - Sửa `LocalOcrPdfConverter` và `LocalOcrImageConverter` nhận tham chiếu `api` (instance của lớp `Api`).
>    - Lưu `self.api = api` để truy cập trạng thái Pause/Abort toàn cục.
> 2. **Kiểm tra Pause/Abort giữa các trang PDF:**
>    - Trong vòng lặp trích xuất text và vòng lặp chạy OCR của `LocalOcrPdfConverter.convert()`, chèn kiểm tra:
>      - Nếu `self.api._scan_aborted` là True: ngắt vòng lặp (`break`).
>      - Nếu `self.api._scan_paused` là True: gọi `self.api._pause_event.wait()` để chặn luồng phụ ngay lập tức.
> 3. **Giải phóng block luồng chính khi Abort:**
>    - Trong khối `finally` của `scan_and_index()`, khi gọi `self.executor.shutdown()`, truyền `wait=not self._scan_aborted`.
>    - Nếu bị Abort, `wait=False` giúp hàm return ngay lập tức về UI, phản hồi "Đã hủy" tức thì cho người dùng.

[ĐỀ_XUẤT_TỐI_ƯU]
- Việc kiểm tra trạng thái ở cấp độ trang (page-level check) giúp ngắt tiến trình nhanh chóng chỉ sau tối đa 1 trang (1-2 giây) thay vì phải đợi cả tài liệu lớn 30-50 trang.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Do `wait=False`, các luồng phụ đang chạy dở sẽ giải phóng ngầm sau đó. Cần đảm bảo các tài nguyên file tạm hoặc trạng thái được dọn dẹp an toàn.

[NEO_HỒI_QUY]
- Đảm bảo logic fallback `pdf_bytes` và cấu hình Tesseract vẫn hoạt động đúng khi truyền tham số `api` mới.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Thay đổi cấu trúc Custom Converters trong [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

```python
class LocalOcrPdfConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api

    def convert(self, file_stream, stream_info, **kwargs):
        # Lấy base_dir và các đường dẫn từ self.api
        base_dir = self.api.base_dir
        base_dir_meipass = self.api.base_dir_meipass
        base_dir_exe = self.api.base_dir_exe
        
        # ... setup tesseract ...

        try:
            with pdfplumber.open(...) as pdf:
                for page in pdf.pages:
                    # Kiểm tra Pause/Abort
                    if self.api._scan_aborted:
                        break
                    if self.api._scan_paused:
                        self.api._pause_event.wait()
                        if self.api._scan_aborted:
                            break
                    # Trích xuất text...
        except Exception:
            pass

        # ... logic OCR ...
        if not full_text or len(full_text) < 100:
            try:
                with pdfplumber.open(...) as pdf:
                    for page_num, page in enumerate(pdf.pages, 1):
                        # Kiểm tra Pause/Abort
                        if self.api._scan_aborted:
                            break
                        if self.api._scan_paused:
                            self.api._pause_event.wait()
                            if self.api._scan_aborted:
                                break
                        # Chạy to_image và OCR...
            except Exception:
                pass
```

### 2. Tắt executor không block luồng chính khi Abort

```python
# Trong scan_and_index():
try:
    self.executor.map(run_single_task, tasks)
finally:
    if self.executor:
        # Nếu bị abort, shutdown ngay lập tức không chờ đợi (wait=False)
        wait_threads = not self._scan_aborted
        self.executor.shutdown(wait=wait_threads)
        self.executor = None
```

## Kế hoạch kiểm thử thủ công (Verification Plan)
1. Chọn một tài liệu PDF lớn (ví dụ trên 30 trang) để quét.
2. Trong lúc app đang chạy OCR tài liệu đó, bấm nút `Pause`. Xác nhận tiến trình dừng ngay lập tức (sau 1-2 giây) và trạng thái UI đổi thành "Đã tạm dừng".
3. Bấm `Resume` để chạy tiếp, sau đó bấm `Abort`. Xác nhận tiến trình hủy lập tức và UI phản hồi "Đã hủy" ngay lập tức không bị đơ.
