# WSR Core Active Loader

- Trước mọi hành động, đọc và tuân thủ `../WSRCore/AGENTS.md`.
- Xác minh build là `WSR-CORE-1.7-RELEASE` qua `../WSRCore/WSR_CONTEXT.json`.
- Nếu router, kernel hoặc command index không đọc được, dừng và báo lỗi.
- Không dùng plan, checkpoint, session hoặc lịch sử để suy diễn quyền phê duyệt.

## Project Safety Overlay

- Xem `runtime/`, `build_artifacts/runtime/`, SQLite, Markdown, HTML cache và index là dữ liệu người dùng có trạng thái.
- `.gitignore` hoặc khả năng tái tạo không làm dữ liệu trở thành an toàn để xóa.
- Trước khi xóa, di chuyển hoặc ghi đè dữ liệu trạng thái, phải kiểm kê chính xác từng đích.
- Phải tạo và kiểm tra backup ngoài đích xóa, trừ khi người dùng miễn backup rõ ràng cho đúng từng đích.
- Phải nhận tín hiệu phê duyệt WSR chính xác sau khi công bố phạm vi cuối cùng.
- Phê duyệt có điều kiện, ngoại lệ hoặc mơ hồ không cấp quyền thực thi.
- Không dùng lệnh clean diện rộng trên `UserData/`, `runtime/` hoặc `build_artifacts/runtime/`.
- Sau cleanup, phải kiểm tra khởi động, trạng thái index và tìm kiếm trước khi tuyên bố hoàn tất.
- Giữ nguyên thay đổi không liên quan của người dùng.
