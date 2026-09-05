# 🚀 gdrive-cli: Quản Lý Google Drive Trên Terminal Linux

Công cụ dòng lệnh (CLI tool) viết bằng Python giúp thao tác, quản lý và xử lý file Google Drive trực tiếp từ Terminal trên Linux với giao diện trực quan, bảng màu đẹp mắt và thanh tiến trình (progress bar).

---

## 📌 Các Tính Năng Chính

- **Liệt kê file & thư mục (`ls`)**: Hiển thị bảng màu Rich với Tên, Loại file, Kích thước (B/KB/MB/GB), Ngày sửa đổi và ID.
- **Tải lên (`upload`)**: Tải file đơn lẻ hoặc tải đệ quy toàn bộ thư mục lên Drive (có thanh tiến trình và resumable upload).
- **Tải xuống (`download`)**: Tải file về máy. Tự động xuất Google Docs -> PDF/DOCX, Google Sheets -> XLSX, Google Slides -> PPTX.
- **Tìm kiếm (`search`)**: Tìm kiếm nhanh theo từ khóa trong tên file/thư mục.
- **Tạo thư mục (`mkdir`)**: Tạo thư mục mới trên Drive.
- **Xóa file (`rm`)**: Chuyển file vào thùng rác hoặc xóa vĩnh viễn (`--permanent`).
- **Chia sẻ file (`share`)**: Bật chế độ chia sẻ công khai qua liên kết (quyền xem, bình luận hoặc chỉnh sửa).
- **Xem thông tin (`info`)**: Xem toàn bộ metadata chi tiết, chủ sở hữu, dung lượng, đường dẫn web.
- **Đọc nhanh (`cat`)**: In trực tiếp nội dung file văn bản từ Drive ra terminal.
- **Kiểm tra dung lượng (`auth status`)**: Hiển thị thanh trạng thái bộ nhớ đã dùng / còn trống và thông tin tài khoản.

---



---

## 📖 Bảng Tra Cứu Lệnh Thường Dùng

| Thao tác | Cú pháp lệnh | Mô tả |
| :--- | :--- | :--- |
| **Kiểm tra tài khoản** | `gdrive auth status` | Xem thông tin tài khoản và dung lượng lưu trữ |
| **Xem danh sách** | `gdrive ls` | Liệt kê file/thư mục ở thư mục gốc |
| **Xem trong thư mục** | `gdrive ls <TÊN_FOLDER_HOẶC_ID>` | Liệt kê nội dung bên trong thư mục (VD: `gdrive ls Nhạc`) |
| **Tìm kiếm file** | `gdrive search "báo cáo"` | Tìm file có chứa từ khóa trong tên |
| **Tải lên 1 file** | `gdrive upload tailieu.pdf` | Tải file lên thư mục gốc |
| **Tải lên vào folder** | `gdrive upload tailieu.pdf -p <TÊN_FOLDER_HOẶC_ID>` | Tải file vào thư mục chỉ định (VD: `-p Nhạc`) |
| **Tải lên cả thư mục** | `gdrive upload ./my_folder/` | Tải đệ quy toàn bộ thư mục lên Drive |
| **Tải file về máy** | `gdrive download <TÊN_FILE_HOẶC_ID>` | Tải file về máy (tự lưu vào thư mục mặc định) |
| **Tải cả thư mục về** | `gdrive download <TÊN_FOLDER_HOẶC_ID>` | Tải đệ quy toàn bộ thư mục về máy |
| **Tải lưu vị trí khác** | `gdrive download <TÊN_FILE_HOẶC_ID> -o ~/Downloads/` | Tải file về thư mục Downloads |
| **Tải xuất dạng PDF** | `gdrive download <TÊN_FILE_HOẶC_ID> --pdf` | Tự động xuất Doc/Sheet thành PDF |
| **Xem thư mục tải mặc định** | `gdrive config download-dir` | Kiểm tra thư mục lưu file tải về hiện tại |
| **Đặt thư mục tải mặc định** | `gdrive config download-dir ~/Downloads` | Tùy chỉnh thư mục tải về mặc định (VD: `~/Downloads`) |
| **Reset thư mục tải về** | `gdrive config reset-download-dir` | Đặt lại về mặc định (lưu tại thư mục đang đứng CWD) |
| **Xem toàn bộ cấu hình** | `gdrive config show` | Xem file config, thư mục tải về, trạng thái auth |
| **Tạo thư mục** | `gdrive mkdir "DuAn2026"` | Tạo thư mục mới trên Drive |
| **Xem thông tin chi tiết**| `gdrive info <TÊN_FILE_HOẶC_ID>` | Xem link web, quyền, kích thước, ngày sửa |
| **Lấy link chia sẻ** | `gdrive share <TÊN_FILE_HOẶC_ID>` | Bật quyền xem cho bất kỳ ai có link |
| **Đọc nhanh file text** | `gdrive cat <TÊN_FILE_HOẶC_ID>` | In nội dung file text ra terminal (VD: `gdrive cat Index.html`) |
| **Xóa file (thùng rác)** | `gdrive rm <TÊN_FILE_HOẶC_ID>` | Chuyển file vào thùng rác |
| **Xóa vĩnh viễn** | `gdrive rm <TÊN_FILE_HOẶC_ID> --permanent` | Xóa hoàn toàn khỏi Drive |
| **Đăng xuất** | `gdrive auth logout` | Xóa token đã lưu |

---

## 💡 Tùy Chọn: Mount Google Drive Thành Ổ Đĩa Cục Bộ Với Rclone

Nếu bạn muốn Google Drive xuất hiện như một ổ cứng trên Linux (để thao tác bằng lệnh `cd`, `cp`, `rsync` hoặc mở bằng File Manager):

1. Cài đặt Rclone 
2. Cấu hình kết nối:
   ```bash
   rclone config
   ```
3. Tạo thư mục mount và gắn ổ:
   ```bash
   mkdir -p ~/GoogleDrive
   rclone mount gdrive: ~/GoogleDrive --vfs-cache-mode writes &
   ```
