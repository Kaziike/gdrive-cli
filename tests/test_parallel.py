import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from gdrive_cli.client import DriveClient


def test_drive_client_thread_local_service(monkeypatch):
    import gdrive_cli.auth as auth
    mock_creds = MagicMock()
    monkeypatch.setattr(auth, "get_credentials", lambda: mock_creds)

    with patch("gdrive_cli.client.build") as mock_build:
        mock_build.side_effect = lambda *args, **kwargs: MagicMock()

        client = DriveClient()
        services = []

        def worker():
            s = client.service
            services.append(s)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(services) == 2
        # Different threads get their own thread-local service instance
        assert services[0] is not services[1]


def test_upload_directory_multithreaded(tmp_path, monkeypatch):
    import gdrive_cli.auth as auth
    monkeypatch.setattr(auth, "get_credentials", lambda: MagicMock())

    with patch("gdrive_cli.client.build") as mock_build:
        mock_build.return_value = MagicMock()
        client = DriveClient()

        # Create dummy directory structure
        root = tmp_path / "my_album"
        sub = root / "vacation"
        sub.mkdir(parents=True)
        (root / "cover.jpg").write_text("image1")
        (sub / "beach.jpg").write_text("image2")
        (sub / "sunset.jpg").write_text("image3")

        uploaded_files = []
        created_folders = []

        client.create_folder = MagicMock(side_effect=lambda name, parent_id=None: created_folders.append(name) or {"id": f"id_{name}"})
        client.upload_file = MagicMock(side_effect=lambda path, parent_id=None, **kwargs: uploaded_files.append((Path(path).name, parent_id)) or {"id": "f_id"})

        res = client.upload_directory(str(root), workers=4)

        assert res["id"] == "id_my_album"
        assert "my_album" in created_folders
        assert "vacation" in created_folders

        file_names = {f[0] for f in uploaded_files}
        assert file_names == {"cover.jpg", "beach.jpg", "sunset.jpg"}


def test_download_folder_multithreaded(tmp_path, monkeypatch):
    import gdrive_cli.auth as auth
    monkeypatch.setattr(auth, "get_credentials", lambda: MagicMock())

    with patch("gdrive_cli.client.build") as mock_build:
        mock_build.return_value = MagicMock()
        client = DriveClient()

        client.get_file_metadata = MagicMock(return_value={"id": "folder_1", "name": "Docs"})

        def mock_list_files(parent_id, page_size=500):
            if parent_id == "folder_1":
                return [
                    {"id": "sub_1", "name": "Projects", "mimeType": "application/vnd.google-apps.folder"},
                    {"id": "file_1", "name": "notes.txt", "mimeType": "text/plain"},
                ]
            elif parent_id == "sub_1":
                return [
                    {"id": "file_2", "name": "report.pdf", "mimeType": "application/pdf"},
                    {"id": "file_3", "name": "budget.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                ]
            return []

        client.list_files = MagicMock(side_effect=mock_list_files)

        downloaded_files = []

        def mock_download_file(file_id, output_dir_or_path=None, **kwargs):
            downloaded_files.append((file_id, output_dir_or_path))
            return Path(output_dir_or_path)

        client.download_file = MagicMock(side_effect=mock_download_file)

        dest = client.download_folder("folder_1", output_dir_or_path=str(tmp_path), workers=4)

        assert dest == tmp_path / "Docs"
        assert (tmp_path / "Docs" / "Projects").is_dir()

        downloaded_ids = {d[0] for d in downloaded_files}
        assert downloaded_ids == {"file_1", "file_2", "file_3"}
