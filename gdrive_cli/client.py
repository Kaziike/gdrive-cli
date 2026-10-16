import io
import os
import threading
import concurrent.futures
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator, Tuple

import click
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from gdrive_cli import auth, ui

EXPORT_MAPPING = {
    "application/vnd.google-apps.document": {
        "ext": ".pdf",
        "mime": "application/pdf",
        "alt_ext": ".docx",
        "alt_mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "application/vnd.google-apps.spreadsheet": {
        "ext": ".xlsx",
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "alt_ext": ".pdf",
        "alt_mime": "application/pdf",
    },
    "application/vnd.google-apps.presentation": {
        "ext": ".pptx",
        "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "alt_ext": ".pdf",
        "alt_mime": "application/pdf",
    },
    "application/vnd.google-apps.drawing": {
        "ext": ".png",
        "mime": "image/png",
        "alt_ext": ".pdf",
        "alt_mime": "application/pdf",
    },
}


class DriveClient:
    def __init__(self):
        self._creds = auth.get_credentials()
        if not self._creds:
            raise PermissionError(
                "Chưa cấu hình xác thực Google Drive! Vui lòng chạy lệnh:\n  gdrive auth setup"
            )
        self._thread_local = threading.local()

    @property
    def service(self):
        if not hasattr(self._thread_local, "service") or self._thread_local.service is None:
            self._thread_local.service = build("drive", "v3", credentials=self._creds, cache_discovery=False)
        return self._thread_local.service

    @service.setter
    def service(self, value):
        self._thread_local.service = value

    def get_about(self) -> Dict[str, Any]:
        """Get account and storage quota info."""
        return self.service.about().get(fields="user,storageQuota").execute()

    def resolve_id(self, identifier: str, is_folder: Optional[bool] = None) -> str:
        """
        Cho phép sử dụng Tên folder/file hoặc ID trực tiếp.
        Nếu truyền 'root' -> trả về 'root'.
        Nếu truyền ID hợp lệ -> trả về ID đó.
        Nếu truyền Tên -> tìm kiếm theo tên và trả về ID tương ứng.
        """
        if not identifier or identifier.strip() == "":
            return "root"

        clean_id = identifier.strip().rstrip("/")
        if clean_id.lower() == "root":
            return "root"

        # 1. Kiểm tra xem clean_id có phải là ID hợp lệ không
        # Thường ID không chứa khoảng trắng hay phần mở rộng file thông dụng
        common_exts = (".pdf", ".png", ".jpg", ".jpeg", ".txt", ".mp4", ".cpp", ".sb3", ".rar", ".zip", ".html", ".docx", ".xlsx", ".pptx", ".sb")
        if " " not in clean_id and not clean_id.endswith(common_exts):
            try:
                meta = self.service.files().get(fileId=clean_id, fields="id, trashed").execute()
                if not meta.get("trashed"):
                    return meta["id"]
            except HttpError:
                pass

        # 2. Tìm kiếm chính xác theo tên (name = '...')
        safe_name = clean_id.replace("'", "\\'")
        q_parts = [f"name = '{safe_name}'", "trashed = false"]
        if is_folder is True:
            q_parts.append("mimeType = 'application/vnd.google-apps.folder'")
        elif is_folder is False:
            q_parts.append("mimeType != 'application/vnd.google-apps.folder'")

        query = " and ".join(q_parts)
        fields = "files(id, name, mimeType, size, modifiedTime, webViewLink, parents)"
        results = (
            self.service.files()
            .list(q=query, pageSize=10, fields=fields, orderBy="modifiedTime desc")
            .execute()
        )
        files = results.get("files", [])

        # Nếu không thấy chính xác, thử tìm kiếm chứa (name contains '...')
        if not files:
            q_contains = [f"name contains '{safe_name}'", "trashed = false"]
            if is_folder is True:
                q_contains.append("mimeType = 'application/vnd.google-apps.folder'")
            elif is_folder is False:
                q_contains.append("mimeType != 'application/vnd.google-apps.folder'")

            query_contains = " and ".join(q_contains)
            results = (
                self.service.files()
                .list(q=query_contains, pageSize=10, fields=fields, orderBy="modifiedTime desc")
                .execute()
            )
            files = results.get("files", [])

        if not files:
            # Fallback: kiểm tra lần cuối nếu đó là một ID hợp lệ có dạng tên file
            try:
                meta = self.service.files().get(fileId=clean_id, fields="id, trashed").execute()
                if not meta.get("trashed"):
                    return meta["id"]
            except Exception:
                pass
            target_desc = "thư mục" if is_folder is True else ("file" if is_folder is False else "file hoặc thư mục")
            raise FileNotFoundError(f"Không tìm thấy {target_desc} nào khớp với tên hoặc ID: '{identifier}'")

        if len(files) == 1:
            return files[0]["id"]

        # Nếu có nhiều hơn 1 file trùng tên
        return self._handle_multiple_matches(clean_id, files)

    def _handle_multiple_matches(self, name: str, files: List[Dict[str, Any]]) -> str:
        ui.print_warning(f"Tìm thấy {len(files)} đối tượng có tên khớp với '{name}':")
        ui.render_file_table(files, title=f"Đối tượng trùng tên '{name}'")
        try:
            choice = click.prompt(
                f"Vui lòng chọn số thứ tự (1-{len(files)}) hoặc nhập ID",
                default="1",
            ).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(files):
                return files[int(choice) - 1]["id"]
            for f in files:
                if f["id"] == choice:
                    return f["id"]
        except Exception:
            pass
        ui.print_info(f"Mặc định chọn đối tượng cập nhật gần nhất: ID {files[0]['id']}")
        return files[0]["id"]


    def list_files(
        self,
        parent_id: Optional[str] = "root",
        query: Optional[str] = None,
        page_size: int = 100,
        order_by: str = "folder,name",
    ) -> List[Dict[str, Any]]:
        """List files and folders in a specified folder or with a query."""
        q_parts = ["trashed = false"]

        if parent_id and not query:
            q_parts.append(f"'{parent_id}' in parents")
        elif query:
            q_parts.append(query)

        q = " and ".join(q_parts)

        fields = "nextPageToken, files(id, name, mimeType, size, modifiedTime, createdTime, webViewLink, webContentLink, parents)"
        results = (
            self.service.files()
            .list(q=q, pageSize=page_size, fields=fields, orderBy=order_by)
            .execute()
        )
        return results.get("files", [])

    def search(self, name: str, page_size: int = 50) -> List[Dict[str, Any]]:
        """Search files by name keyword."""
        safe_name = name.replace("'", "\\'")
        q = f"trashed = false and name contains '{safe_name}'"
        fields = "files(id, name, mimeType, size, modifiedTime, webViewLink, parents)"
        results = (
            self.service.files()
            .list(q=q, pageSize=page_size, fields=fields, orderBy="folder,modifiedTime desc")
            .execute()
        )
        return results.get("files", [])

    def get_file_metadata(self, file_id: str, fields: str = "*") -> Dict[str, Any]:
        """Fetch metadata for a given file ID."""
        return self.service.files().get(fileId=file_id, fields=fields).execute()

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new folder in Google Drive."""
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        return (
            self.service.files()
            .create(body=metadata, fields="id, name, webViewLink")
            .execute()
        )

    def find_folder(self, name: str, parent_id: str = "root") -> Optional[Dict[str, Any]]:
        """Tìm thư mục con theo tên chính xác trong một thư mục cha."""
        safe_name = name.replace("'", "\\'")
        q = f"name = '{safe_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res = self.service.files().list(q=q, pageSize=1, fields="files(id, name)").execute()
        files = res.get("files", [])
        return files[0] if files else None

    def ensure_drive_path(self, path_components: List[str], root_parent_id: str = "root") -> str:
        """
        Đảm bảo cấu trúc thư mục phân cấp lồng nhau tồn tại trên Google Drive.
        Trả về ID của thư mục lá cuối cùng.
        Có bộ nhớ cache bộ nhớ tạm để tránh gọi API nhiều lần.
        """
        if not hasattr(self, "_folder_path_cache"):
            self._folder_path_cache = {}

        current_id = root_parent_id
        current_path_acc = []

        for comp in path_components:
            current_path_acc.append(comp)
            cache_key = (current_id, tuple(current_path_acc))
            if cache_key in self._folder_path_cache:
                current_id = self._folder_path_cache[cache_key]
                continue

            existing = self.find_folder(comp, parent_id=current_id)
            if existing:
                folder_id = existing["id"]
            else:
                created = self.create_folder(comp, parent_id=current_id)
                folder_id = created["id"]

            self._folder_path_cache[cache_key] = folder_id
            current_id = folder_id

        return current_id

    def upload_file(
        self,
        local_path: str,
        parent_id: Optional[str] = None,
        progress_callback=None,
        chunk_size: int = 5 * 1024 * 1024,
    ) -> Dict[str, Any]:
        """Upload a single file with resumable chunked upload."""
        src_path = Path(local_path).expanduser().resolve()
        if not src_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy file: {src_path}")

        mime_type, _ = mimetypes.guess_type(str(src_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        file_metadata = {"name": src_path.name}
        if parent_id:
            file_metadata["parents"] = [parent_id]

        media = MediaFileUpload(
            str(src_path),
            mimetype=mime_type,
            resumable=True,
            chunksize=chunk_size,
        )

        request = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, size, webViewLink, mimeType",
        )

        response = None
        total_size = src_path.stat().st_size
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback(status.resumable_progress, total_size)

        if progress_callback:
            progress_callback(total_size, total_size)

        return response

    def upload_directory(
        self,
        local_dir_path: str,
        parent_id: Optional[str] = None,
        on_item_upload=None,
        on_progress=None,
        workers: int = 4,
    ) -> Dict[str, Any]:
        """
        Recursively upload a folder and its contents.
        Supports parallel upload with multiple workers.
        Returns the created root folder metadata.
        """
        root_dir = Path(local_dir_path).expanduser().resolve()
        if not root_dir.is_dir():
            raise NotADirectoryError(f"Không phải thư mục: {root_dir}")

        root_folder_meta = self.create_folder(root_dir.name, parent_id=parent_id)
        folder_map = {root_dir: root_folder_meta["id"]}

        IGNORE_DIRS = {"venv", ".venv", "__pycache__", ".git", ".pytest_cache", "node_modules"}

        files_to_upload: List[Tuple[Path, str]] = []

        for current_path, subdirs, files in os.walk(root_dir):
            # Bỏ qua các thư mục rác, môi trường ảo
            subdirs[:] = [d for d in subdirs if d not in IGNORE_DIRS and not d.endswith(".egg-info")]
            valid_files = [f for f in files if not f.endswith((".pyc", ".pyo")) and f != ".DS_Store"]

            current_p = Path(current_path)
            current_remote_id = folder_map[current_p]

            # Tạo cây thư mục con trên Drive
            for subdir_name in subdirs:
                sub_p = current_p / subdir_name
                sub_meta = self.create_folder(subdir_name, parent_id=current_remote_id)
                folder_map[sub_p] = sub_meta["id"]

            for file_name in valid_files:
                file_p = current_p / file_name
                files_to_upload.append((file_p, current_remote_id))

        if not files_to_upload:
            return root_folder_meta

        def _upload_worker(item):
            file_p, target_folder_id = item
            if on_item_upload:
                on_item_upload(file_p)
            res = self.upload_file(str(file_p), parent_id=target_folder_id)
            if on_progress:
                on_progress(file_p)
            return res

        num_workers = max(1, min(workers, len(files_to_upload)))
        if num_workers <= 1:
            for it in files_to_upload:
                _upload_worker(it)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(_upload_worker, it) for it in files_to_upload]
                for f in concurrent.futures.as_completed(futures):
                    f.result()

        return root_folder_meta

    def download_file(
        self,
        file_id: str,
        output_dir_or_path: Optional[str] = None,
        progress_callback=None,
        prefer_docx_or_xlsx: bool = True,
    ) -> Path:
        """
        Download a file by ID.
        Automatically handles Google Docs/Sheets/Slides export.
        """
        meta = self.get_file_metadata(file_id, fields="id, name, mimeType, size")
        name = meta.get("name", file_id)
        mime = meta.get("mimeType", "")
        file_size = int(meta.get("size", 0)) if meta.get("size") else 0

        is_google_doc = mime in EXPORT_MAPPING
        export_mime = None

        if is_google_doc:
            info = EXPORT_MAPPING[mime]
            if prefer_docx_or_xlsx and "alt_mime" in info and ("wordprocessingml" in info["alt_mime"] or "spreadsheetml" in info["alt_mime"] or "presentationml" in info["alt_mime"]):
                export_mime = info["alt_mime"]
                ext = info["alt_ext"]
            else:
                export_mime = info["mime"]
                ext = info["ext"]

            if not name.endswith(ext):
                name = name + ext

        # Determine target file path
        if output_dir_or_path:
            out = Path(output_dir_or_path).expanduser().resolve()
            if out.is_dir():
                target_path = out / name
            else:
                target_path = out
        else:
            target_path = Path.cwd() / name

        target_path.parent.mkdir(parents=True, exist_ok=True)

        if is_google_doc:
            request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = self.service.files().get_media(fileId=file_id)

        with open(target_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request, chunksize=2 * 1024 * 1024)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status and progress_callback:
                    progress_callback(status.resumable_progress, status.total_size or file_size)

            if progress_callback:
                progress_callback(target_path.stat().st_size, target_path.stat().st_size)

        return target_path

    def download_folder(
        self,
        folder_id: str,
        output_dir_or_path: Optional[str] = None,
        on_item_download=None,
        on_progress=None,
        workers: int = 4,
    ) -> Path:
        """
        Tải đệ quy toàn bộ thư mục và các file bên trong về máy.
        Hỗ trợ tải song song đa luồng (workers).
        """
        meta = self.get_file_metadata(folder_id, fields="id, name")
        folder_name = meta.get("name", folder_id)

        base_dir = Path(output_dir_or_path).expanduser().resolve() if output_dir_or_path else Path.cwd()
        target_dir = base_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Duyệt cây thư mục từ Drive
        folders_to_visit = [(folder_id, target_dir)]
        files_to_download: List[Tuple[str, str, Path]] = []  # (item_id, item_name, dest_dir)

        while folders_to_visit:
            curr_id, curr_local_dir = folders_to_visit.pop(0)
            items = self.list_files(parent_id=curr_id, page_size=500)
            for item in items:
                item_id = item["id"]
                item_name = item.get("name", "Unnamed")
                item_mime = item.get("mimeType", "")

                if item_mime == "application/vnd.google-apps.folder":
                    sub_local_dir = curr_local_dir / item_name
                    sub_local_dir.mkdir(parents=True, exist_ok=True)
                    folders_to_visit.append((item_id, sub_local_dir))
                else:
                    files_to_download.append((item_id, item_name, curr_local_dir))

        if not files_to_download:
            return target_dir

        def _dl_worker(it):
            item_id, item_name, dest_dir = it
            if on_item_download:
                on_item_download(item_name)
            res = self.download_file(item_id, output_dir_or_path=str(dest_dir))
            if on_progress:
                on_progress(item_name)
            return res

        num_workers = max(1, min(workers, len(files_to_download)))
        if num_workers <= 1:
            for it in files_to_download:
                _dl_worker(it)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(_dl_worker, it) for it in files_to_download]
                for f in concurrent.futures.as_completed(futures):
                    f.result()

        return target_dir

    def delete_file(self, file_id: str, permanent: bool = False) -> None:
        """Trash or permanently delete a file/folder."""
        if permanent:
            self.service.files().delete(fileId=file_id).execute()
        else:
            self.service.files().update(fileId=file_id, body={"trashed": True}).execute()

    def share_file(self, file_id: str, role: str = "reader", share_type: str = "anyone") -> str:
        """
        Set sharing permissions and return the webViewLink.
        role: 'reader', 'commenter', 'writer'
        type: 'anyone', 'user', 'group', 'domain'
        """
        permission = {
            "type": share_type,
            "role": role,
        }
        self.service.permissions().create(fileId=file_id, body=permission).execute()
        meta = self.service.files().get(fileId=file_id, fields="webViewLink").execute()
        return meta.get("webViewLink", "")

    def cat_file(self, file_id: str) -> str:
        """Read content of a text file or export Google Doc as plain text."""
        meta = self.get_file_metadata(file_id, fields="id, name, mimeType")
        mime = meta.get("mimeType", "")

        fh = io.BytesIO()
        if mime == "application/vnd.google-apps.document":
            request = self.service.files().export_media(fileId=file_id, mimeType="text/plain")
        else:
            request = self.service.files().get_media(fileId=file_id)

        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        fh.seek(0)
        return fh.read().decode("utf-8", errors="replace")
