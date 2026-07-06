---
task_name: "Fix lỗi dọn dẹp nhầm MARKDOWN: Chuyển thư mục MARKDOWN về cục bộ từng folder"
date: "2026-07-03"
version: "v1"
status: "Draft"
target_files:
  - "d:/CICT BACKUP/CICT PROCEDURES/MDBANK/src/app.py"
---

# Quy hoạch chuyển thư mục MARKDOWN về cục bộ từng thư mục quét

> [!TIP]
> ### [HIỂU_YÊU_CẦU]
> 1. **Khắc phục lỗi mất dữ liệu index:** Khi quét folder mới, app xóa sạch chỉ mục `.md` của các folder khác trong thư mục `MARKDOWN` chung.
> 2. **Chuyển MARKDOWN về cục bộ:** Khi quét bất kỳ thư mục nào (mặc định hay tùy chọn), thư mục `MARKDOWN` sẽ được tạo ngay **TẠI CHÍNH THƯ MỤC ĐÓ** (`scan_target/MARKDOWN`).
> 3. **Bỏ cơ chế ORIGINAL:** Bỏ hoàn toàn cơ chế di chuyển/sao lưu file gốc vào thư mục `ORIGINAL` ở cả chế độ mặc định và tùy chọn. Không di chuyển file gốc.
> 4. **Bảo toàn dữ liệu khác:** Giữ nguyên các cơ chế lưu thông tin ở `data/` (`SSFolder.txt`, `search_db.js`, `search_db_[hash].js`) và logic UI.

## Phạm vi Thay đổi (Impact Scope)
- [ ] [MODIFY] [app.py](file:///d:/CICT%20BACKUP/CICT%20PROCEDURES/MDBANK/src/app.py)

## Điểm neo Hành vi cốt lõi (Behavioral Memory Anchors)
- Bảo toàn logic trích xuất metadata (Domain, Doc Type, Language, Year) từ nội dung file.
- Định dạng database JS được tạo ra (`var SEARCH_DB = ...`) không đổi cấu trúc.

## [PHƯƠNG_PHÁP]

### Backend (Python)
1. **Xác định lại `markdown_root`:**
   - Đặt `markdown_root = os.path.join(scan_target, 'MARKDOWN')`.
   - Loại bỏ hoàn toàn khai báo và tạo thư mục `original_root`.
2. **Thống nhất logic quét và tạo chỉ mục:**
   - Xóa bỏ phân nhánh `if scan_target == self.base_dir:` trong `scan_and_index()`.
   - Áp dụng duy nhất một luồng quét không di chuyển file gốc (logic của nhánh `else` cũ) cho tất cả các thư mục quét.
   - Khi quét qua các thư mục con của `scan_target`, bỏ qua thư mục `MARKDOWN` của chính nó (đã được cấu hình trong loại trừ là `'markdown'`).
3. **Đơn giản hóa đường dẫn gốc trong database:**
   - Đặt `original_rel_path` tương đối với `scan_target`.
   - Đặt `absolute_original_path` trỏ trực tiếp đến vị trí gốc của file trong `scan_target`.

[ĐỀ_XUẤT_TỐI_ƯU]
- Bằng cách đặt thư mục `MARKDOWN` trực tiếp trong thư mục quét, mỗi thư mục sẽ tự quản lý bộ nhớ đệm index `.md` của riêng mình, loại bỏ nguy cơ ghi đè/xóa nhầm chỉ mục giữa các thư mục khác nhau.

[CẢNH_BÁO]
- Khi người dùng quét thư mục mặc định `self.base_dir`, thư mục `MARKDOWN` cũng sẽ nằm tại `self.base_dir/MARKDOWN` (như cũ), nhưng các file gốc sẽ không bị di chuyển vào `ORIGINAL`. Do đó, người dùng cần lưu ý không chỉnh sửa thủ công các file trong `MARKDOWN`.

[NEO_HỒI_QUY]
- Đảm bảo cơ chế mở thư mục chứa file gốc bằng `open_explorer` vẫn hoạt động chính xác với `absolute_original_path` trỏ trực tiếp vào file nguồn.

## Kiến trúc Giải thuật & Mã giả (Architecture & Pseudocode)

### Cải tiến `scan_and_index` trong Python (`app.py`)
```python
def scan_and_index(self):
    # ... khởi tạo MarkItDown ...

    # Xác định thư mục quét mục tiêu
    scan_target = self.scan_dir if self.scan_dir else self.base_dir
    if not os.path.exists(scan_target):
        return {"success": False, "error": f"Thư mục quét không tồn tại: {scan_target}"}

    # Tạo thư mục MARKDOWN tại chính thư mục quét
    markdown_root = os.path.join(scan_target, 'MARKDOWN')
    os.makedirs(markdown_root, exist_ok=True)

    expected_markdown_files = set()
    tasks = []

    # Quét thống nhất cho tất cả các thư mục (Không phân biệt mặc định/tùy chọn)
    for root, dirs, files in os.walk(scan_target):
        rel_parts = set(os.path.relpath(root, scan_target).lower().replace('\\', '/').split('/'))
        # Bỏ qua các thư mục hệ thống và chính thư mục 'markdown'
        if rel_parts & {'__pycache__', 'build', 'dist', '.git', '.gemini', '.agents', 'markdown', 'original', 'src', 'docs', 'data', 'logs', 'build_temp', 'lib', 'scr', 'node_modules', '.vs', '.vscode'}:
            continue
        for file in files:
            if file.startswith('~$'):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in supported_extensions:
                file_path = os.path.join(root, file)
                rel_dir = os.path.relpath(root, scan_target)
                if rel_dir == '.':
                    rel_dir = ''
                
                dest_markdown_dir = os.path.join(markdown_root, rel_dir)
                os.makedirs(dest_markdown_dir, exist_ok=True)
                new_markdown_path = os.path.join(dest_markdown_dir, file + ".md")
                
                expected_markdown_files.add(os.path.normpath(new_markdown_path))
                
                if not os.path.exists(new_markdown_path):
                    tasks.append({
                        'src_path': file_path,
                        'dest_md_path': new_markdown_path,
                        'dest_orig_path': None, # Không di chuyển file gốc
                        'clean_src_after': False
                    })
            elif ext == '.md':
                file_path = os.path.join(root, file)
                rel_dir = os.path.relpath(root, scan_target)
                if rel_dir == '.':
                    rel_dir = ''
                
                dest_markdown_dir = os.path.join(markdown_root, rel_dir)
                os.makedirs(dest_markdown_dir, exist_ok=True)
                new_markdown_path = os.path.join(dest_markdown_dir, file)
                
                expected_markdown_files.add(os.path.normpath(new_markdown_path))
                
                if not os.path.exists(new_markdown_path):
                    try:
                        shutil.copy2(file_path, new_markdown_path)
                    except Exception as e:
                        print(f"Error copying md file {file_path}: {e}")

    # ... phần thực thi đa luồng run_single_task ...
    # ... phần dọn dẹp các tệp mồ côi và thư mục rỗng trong markdown_root cục bộ ...

    # Duyệt để tạo database search_db.js
    db_entries = []
    for root, dirs, files in os.walk(markdown_root):
        # ... loại trừ thư mục hệ thống ...
        for file in files:
            if file.lower().endswith('.md'):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.base_dir).replace('\\', '/')
                
                category, size, cleaned_content = self._classify_file(filepath, rel_path)
                if category == "Real Content":
                    # ... trích xuất metadata ...
                    original_filename = file[:-3] if file.lower().endswith('.md') else file
                    rel_markdown_subdir = os.path.relpath(root, markdown_root)
                    if rel_markdown_subdir == '.':
                        rel_markdown_subdir = ''
                    
                    original_rel_path = os.path.join(rel_markdown_subdir, original_filename).replace('\\', '/')
                    absolute_original_path = os.path.abspath(os.path.join(scan_target, rel_markdown_subdir, original_filename))
                    
                    db_entries.append({
                        "title": original_filename,
                        "path": rel_path,
                        "original_path": original_rel_path,
                        "absolute_original_path": absolute_original_path,
                        # ... metadata khác ...
                    })
```

## Verification Plan

### Manual Verification
1. Dọn dẹp thử một số file trong thư mục `ORIGINAL` cũ (hoặc di chuyển chúng về lại thư mục gốc mặc định nếu cần).
2. Chạy ứng dụng, chọn thư mục mặc định và bấm "Quét và index".
3. Xác nhận thư mục `MARKDOWN` được tạo tại thư mục gốc, chứa các file chỉ mục `.md`. File gốc không bị di chuyển vào thư mục `ORIGINAL`.
4. Chọn một thư mục ngoài tùy chỉnh, bấm "Quét và index".
5. Xác nhận:
   - Thư mục `MARKDOWN` được tạo ngay bên trong thư mục ngoài đó.
   - Thư mục `MARKDOWN` ở thư mục mặc định không hề bị ảnh hưởng (không bị xóa file).
   - Có thể tìm kiếm bình thường và mở file gốc trực tiếp từ kết quả tìm kiếm của cả hai thư mục quét.
