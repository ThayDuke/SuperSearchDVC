---
task_name: "Fix lỗi ValueError mount đĩa và tối ưu Pause/Abort tiến trình quét"
date: "2026-07-03"
version: "v2"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
---

# Lập kế hoạch sửa lỗi mount đĩa và tối ưu nút Pause/Abort

> [!TIP]
> ### [HIỂU_YÊU_CẦU] (Confidence Score: 10/10)
> 1. **Vấn đề quét lại file đã hoàn thành:** Người dùng nghi ngờ app quét lại file cũ. Cần khẳng định logic: App không convert lại file md đã tồn tại và không lỗi. Tuy nhiên, app vẫn duyệt và phân tích toàn bộ file md để nạp database JS.
> 2. **Lỗi ValueError mount đĩa:** Lỗi xảy ra khi tính `os.path.relpath(filepath, self.base_dir)` giữa 2 ổ đĩa khác nhau (C: và D:). Cần bọc xử lý lỗi và fallback về đường dẫn tuyệt đối.
> 3. **Lỗi Pause/Abort đa luồng:** Khi bấm Abort, ThreadPoolExecutor block tiến trình chính cho đến khi tất cả các task (kể cả task bị bỏ qua) duyệt xong. Cần tắt executor ngay lập tức bằng `shutdown(cancel_futures=True)`.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Bảo toàn logic khôi phục file từ `ORIGINAL` và phát hiện file md lỗi cũ.
- Giữ nguyên cấu trúc database JSON lưu trong `search_db.js`.

> [!NOTE]
> ### [PHƯƠNG_PHÁP]
> 1. **Khắc phục ValueError:**
>    - Trong `scan_and_index()`, tại đoạn tính `rel_path` của file `.md`, bọc trong khối `try-except ValueError`.
>    - Nếu xảy ra lỗi khác phân vùng mount, fallback đặt `rel_path` bằng đường dẫn tuyệt đối của file.
> 2. **Tối ưu Pause/Abort:**
>    - Lưu instance `ThreadPoolExecutor` vào thuộc tính `self.executor` của class `Api`.
>    - Khi bấm `abort_scan()`, nếu `self.executor` đang chạy, gọi `self.executor.shutdown(wait=False, cancel_futures=True)` để hủy bỏ ngay lập tức toàn bộ task chưa thực thi trong hàng đợi.
>    - Sửa logic dừng trong `run_single_task()` để thoát nhanh khi `self._scan_aborted` được bật.
> 3. **Loại bỏ file md lỗi khỏi DB:**
>    - Trong `_classify_file()`, nếu nội dung file md chứa `"Error during local OCR:"`, trả về `"Error Reading"` để hệ thống không index file lỗi vào DB.

[ĐỀ_XUẤT_TỐI_ƯU]
- Việc sử dụng `cancel_futures=True` sẽ giải phóng lập tức tài nguyên hàng đợi và trả quyền điều khiển về UI nhanh chóng, tránh cảm giác app bị đơ/treo khi hủy quét thư mục lớn.

> [!WARNING]
> ### [CẢNH_BÁO]
> - Khi gọi `executor.shutdown(wait=False)`, luồng chính sẽ không đợi các luồng phụ đang chạy dở kết thúc. Do đó, các file đang được OCR dở vẫn sẽ tiếp tục chạy ngầm cho đến khi xong file đó, nhưng hàng đợi mới sẽ bị chặn hoàn toàn.

[NEO_HỒI_QUY]
- Đảm bảo logic đồng bộ hóa `self.lock` khi cập nhật trạng thái tiến trình quét lên UI không bị xung đột luồng khi executor bị shutdown đột ngột.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### 1. Khắc phục lỗi mount đĩa trong `scan_and_index`

```python
# Trong scan_and_index quét file md tạo DB:
for file in files:
    if file.lower().endswith('.md'):
        filepath = os.path.join(root, file)
        # Bọc rel_path để tránh ValueError khi khác mount drive (C: và D:)
        try:
            rel_path = os.path.relpath(filepath, self.base_dir).replace('\\', '/')
        except ValueError:
            rel_path = os.path.abspath(filepath).replace('\\', '/')
```

### 2. Quản lý và hủy nhanh Executor khi Abort

```python
# Trong Api class:
def __init__(self, base_dir):
    # ...
    self.executor = None

def abort_scan(self):
    self._scan_aborted = True
    self._pause_event.set()
    # Tắt executor ngay lập tức, hủy các task trong hàng đợi
    if self.executor:
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
    return {"success": True}

def scan_and_index(self):
    # ...
    if total_tasks > 0:
        workers = self.get_safe_workers_count()
        # Khởi tạo executor và lưu vào self.executor
        self.executor = ThreadPoolExecutor(max_workers=workers)
        try:
            self.executor.map(run_single_task, tasks)
        finally:
            self.executor.shutdown(wait=True)
            self.executor = None
```

## Kế hoạch kiểm thử thủ công (Verification Plan)
1. Thử quét một thư mục nằm trên ổ đĩa khác với ổ đĩa cài đặt ứng dụng (ví dụ quét ổ C: khi app ở ổ D:). Xác nhận không còn lỗi ValueError.
2. Bấm quét thư mục lớn, trong lúc đang quét bấm `Abort` và `Pause`. Xác nhận tiến trình dừng ngay lập tức và UI phản hồi nhanh chóng.
