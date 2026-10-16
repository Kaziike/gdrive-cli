import os
import sys
import json
import shutil
import socket
import fnmatch
import tarfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from rich.table import Table
from rich import box

from gdrive_cli import ui
from gdrive_cli.client import DriveClient

BACKUP_ROOT_DIR = "Linux_Backups"

# Các thư mục rác, bộ đệm tạm thời phổ biến cần loại bỏ để tránh phình dung lượng
DEFAULT_EXCLUDE_DIRS = {
    "cache", "Cache", ".cache", "GPUCache", "Code Cache", "ShaderCache",
    "Crashpad", "Crash Reports", "Trash", ".Trash", ".Trash-1000",
    "node_modules", "venv", ".venv", "__pycache__", "Service Worker",
    "CacheStorage", "logs", ".git", ".pytest_cache",
    "Steam/steamapps", "flatpak/repo", "browser/Default/Cache",
    "google-chrome/Default/Cache", "chromium/Default/Cache",
    "BraveSoftware/Brave-Browser/Default/Cache", "discord/Cache",
}

# Các file rác hoặc socket / lock không thể hoặc không nên sao lưu
DEFAULT_EXCLUDE_FILES = {
    "*.sock", "*.socket", "*.lock", "*.tmp", "*.swp", "*.log",
    "*.pma", "*.pid", ".DS_Store"
}

# Ánh xạ tên thư mục config sang tên gói phần mềm tương ứng
KNOWN_APP_MAP = {
    "nvim": "neovim",
    "fish": "fish",
    "kitty": "kitty",
    "alacritty": "alacritty",
    "foot": "foot",
    "wezterm": "wezterm",
    "hypr": "hyprland",
    "waybar": "waybar",
    "rofi": "rofi",
    "wofi": "wofi",
    "fastfetch": "fastfetch",
    "neofetch": "neofetch",
    "btop": "btop",
    "htop": "htop",
    "mpv": "mpv",
    "zsh": "zsh",
    "tmux": "tmux",
    "starship": "starship",
    "dunst": "dunst",
    "mako": "mako",
    "sway": "sway",
    "i3": "i3-wm",
    "polybar": "polybar",
    "ranger": "ranger",
    "yazi": "yazi",
    "lazygit": "lazygit",
    "obs-studio": "obs-studio",
    "Code": "visual-studio-code-bin",
    "VSCodium": "vscodium-bin",
    "google-chrome": "google-chrome",
    "chromium": "chromium",
    "brave-browser": "brave-bin",
    "firefox": "firefox",
    "discord": "discord",
    "spotify": "spotify",
    "gimp": "gimp",
    "inkscape": "inkscape",
    "vlc": "vlc",
    "docker": "docker",
    "git": "git",
    "thunar": "thunar",
    "dolphin": "dolphin",
}


class BackupItem:
    def __init__(self, local_path: Path, rel_path: str, size: int):
        self.local_path = local_path
        self.rel_path = rel_path.lstrip("/")
        self.size = size


def detect_package_manager() -> Optional[str]:
    """Phát hiện trình quản lý gói có trên hệ thống"""
    for pm in ["yay", "paru", "pacman", "flatpak", "apt", "dnf"]:
        if shutil.which(pm):
            return pm
    return None


def export_system_packages() -> Dict[str, List[str]]:
    """Ghi nhận danh sách gói phần mềm đã cài đặt trên máy"""
    packages = {}
    try:
        if shutil.which("pacman"):
            res = subprocess.run(["pacman", "-Qqe"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                packages["pacman_native"] = res.stdout.strip().splitlines()

            # AUR packages qua pacman -Qqm
            res_aur = subprocess.run(["pacman", "-Qqm"], capture_output=True, text=True, check=False)
            if res_aur.returncode == 0:
                packages["pacman_aur"] = res_aur.stdout.strip().splitlines()

        if shutil.which("flatpak"):
            res_flatpak = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                capture_output=True, text=True, check=False
            )
            if res_flatpak.returncode == 0:
                packages["flatpak"] = res_flatpak.stdout.strip().splitlines()
    except Exception:
        pass
    return packages


def check_app_installed(app_or_pkg_name: str) -> bool:
    """Kiểm tra xem ứng dụng hoặc gói đã được cài đặt trên máy chưa"""
    # 1. Kiểm tra binary trong PATH
    if shutil.which(app_or_pkg_name):
        return True

    # 2. Kiểm tra qua pacman
    if shutil.which("pacman"):
        res = subprocess.run(["pacman", "-Qi", app_or_pkg_name], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return True

    # 3. Kiểm tra qua flatpak
    if shutil.which("flatpak"):
        res = subprocess.run(["flatpak", "info", app_or_pkg_name], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return True

    return False


def install_application(pkg_name: str) -> bool:
    """Cài đặt ứng dụng qua yay, pacman hoặc flatpak"""
    pm = detect_package_manager()
    if not pm:
        ui.print_error("Không tìm thấy trình quản lý gói phù hợp (yay, pacman, flatpak).")
        return False

    ui.print_info(f"Đang tiến hành cài đặt [bold cyan]{pkg_name}[/bold cyan] bằng [bold]{pm}[/bold]...")
    try:
        if pm in ["yay", "paru"]:
            cmd = [pm, "-S", "--noconfirm", pkg_name]
        elif pm == "pacman":
            cmd = ["sudo", "pacman", "-S", "--noconfirm", pkg_name]
        elif pm == "flatpak":
            cmd = ["flatpak", "install", "-y", pkg_name]
        elif pm == "apt":
            cmd = ["sudo", "apt", "install", "-y", pkg_name]
        else:
            cmd = ["sudo", pm, "install", "-y", pkg_name]

        res = subprocess.run(cmd)
        if res.returncode == 0:
            ui.print_success(f"Đã cài đặt thành công: [bold]{pkg_name}[/bold]")
            return True
        else:
            ui.print_error(f"Lỗi khi cài đặt {pkg_name} (exit code: {res.returncode})")
            return False
    except Exception as e:
        ui.print_error(f"Thất bại khi cài đặt {pkg_name}: {e}")
        return False


def is_path_excluded(
    path: Path,
    rel_path: Optional[Path] = None,
    custom_excludes: Optional[List[str]] = None
) -> bool:
    """Kiểm tra đường dẫn có thuộc danh sách loại trừ không"""
    check_parts = set(rel_path.parts) if rel_path else set(path.parts)
    name = path.name

    # 1. Kiểm tra thư mục loại trừ dựa trên tên hoặc các thành phần tương đối
    for exc in DEFAULT_EXCLUDE_DIRS:
        if exc in check_parts or name == exc:
            return True
        if "/" in exc:
            rel_str = str(rel_path) if rel_path else name
            if exc in rel_str:
                return True

    # 2. Kiểm tra mẫu file loại trừ
    for pat in DEFAULT_EXCLUDE_FILES:
        if fnmatch.fnmatch(name, pat):
            return True

    # 3. Custom excludes
    if custom_excludes:
        for pat in custom_excludes:
            if fnmatch.fnmatch(name, pat) or (rel_path and fnmatch.fnmatch(str(rel_path), pat)):
                return True

    # 4. Bỏ qua socket, fifo, broken symlinks
    if path.is_symlink() and not path.exists():
        return True
    try:
        if path.is_socket() or path.is_fifo():
            return True
    except Exception:
        return True

    return False


def resolve_backup_targets(
    raw_targets: List[str],
    install_missing: bool = False
) -> Tuple[List[Tuple[Path, str]], List[str]]:
    """
    Phân giải các target đầu vào (preset như 'config', 'appdata', hoặc đường dẫn/tên app cụ thể).
    Trả về: (Danh sách (Path_gốc, rel_prefix), Danh sách các ứng dụng được phát hiện).
    """
    home = Path.home()
    resolved_paths: List[Tuple[Path, str]] = []
    detected_apps: List[str] = []

    if not raw_targets:
        # Mặc định sao lưu config
        raw_targets = ["config"]

    for t in raw_targets:
        t_clean = t.strip().rstrip("/")

        # Preset 'config' -> ~/.config
        if t_clean.lower() == "config":
            config_dir = home / ".config"
            if config_dir.is_dir():
                resolved_paths.append((config_dir, ".config"))
                # Quét các app trong ~/.config
                for sub in config_dir.iterdir():
                    if sub.is_dir() and not sub.name.startswith("."):
                        app_pkg = KNOWN_APP_MAP.get(sub.name, sub.name)
                        detected_apps.append(app_pkg)

                if install_missing:
                    missing = [app for app in set(detected_apps) if not check_app_installed(app)]
                    if missing:
                        ui.print_info(f"Phát hiện {len(missing)} ứng dụng chưa cài đặt: {', '.join(missing)}")
                        for app in missing:
                            install_application(app)

        # Preset 'appdata' -> ~/.local/share
        elif t_clean.lower() == "appdata":
            appdata_dir = home / ".local" / "share"
            if appdata_dir.is_dir():
                resolved_paths.append((appdata_dir, ".local/share"))

        # Preset 'dotfiles' -> các file cấu hình tại home
        elif t_clean.lower() == "dotfiles":
            for dotfile in [".bashrc", ".zshrc", ".profile", ".gitconfig", ".p10k.zsh"]:
                p = home / dotfile
                if p.is_file():
                    resolved_paths.append((p, dotfile))

        # Kiểm tra xem có phải tên ứng dụng trong ~/.config không (VD: nvim, kitty, fish)
        elif (home / ".config" / t_clean).is_dir():
            target_p = home / ".config" / t_clean
            resolved_paths.append((target_p, f".config/{t_clean}"))
            app_pkg = KNOWN_APP_MAP.get(t_clean, t_clean)
            detected_apps.append(app_pkg)

            # Kiểm tra ứng dụng đã cài chưa
            if not check_app_installed(app_pkg):
                ui.print_warning(f"Ứng dụng tương ứng với cấu hình '{t_clean}' ([bold cyan]{app_pkg}[/bold cyan]) chưa được cài đặt trên máy!")
                if install_missing:
                    install_application(app_pkg)
                else:
                    try:
                        import click
                        if click.confirm(f"Bạn có muốn cài đặt '{app_pkg}' ngay bây giờ không?"):
                            install_application(app_pkg)
                    except Exception:
                        pass

        # Kiểm tra nếu người dùng truyền tên ứng dụng đã biết (kể cả khi chưa tạo folder config)
        elif t_clean in KNOWN_APP_MAP or t_clean in KNOWN_APP_MAP.values():
            app_pkg = KNOWN_APP_MAP.get(t_clean, t_clean)
            config_name = next((k for k, v in KNOWN_APP_MAP.items() if v == t_clean), t_clean)
            target_p = home / ".config" / config_name

            if not check_app_installed(app_pkg):
                ui.print_warning(f"Ứng dụng '{app_pkg}' chưa được cài đặt trên máy!")
                if install_missing:
                    install_application(app_pkg)
                else:
                    try:
                        import click
                        if click.confirm(f"Bạn có muốn cài đặt '{app_pkg}' ngay bây giờ không?"):
                            install_application(app_pkg)
                    except Exception:
                        pass

            if target_p.exists():
                resolved_paths.append((target_p, f".config/{config_name}"))
                detected_apps.append(app_pkg)
            else:
                ui.print_info(f"Ứng dụng '{app_pkg}' chưa có file cấu hình tại {target_p}.")

        # Đường dẫn file hoặc thư mục cụ thể
        else:
            p = Path(t_clean).expanduser().resolve()
            if p.exists():
                try:
                    rel_to_home = p.relative_to(home)
                    resolved_paths.append((p, str(rel_to_home)))
                except ValueError:
                    resolved_paths.append((p, p.name))
            else:
                ui.print_warning(f"Bỏ qua: Không tìm thấy đường dẫn hoặc ứng dụng '{t}'")

    return resolved_paths, list(set(detected_apps))


def collect_backup_items(
    resolved_targets: List[Tuple[Path, str]],
    custom_excludes: Optional[List[str]] = None,
) -> Tuple[List[BackupItem], int]:
    """Quét tất cả các file cần sao lưu và bảo toàn cấu trúc thư mục"""
    items: List[BackupItem] = []
    total_bytes = 0

    for src_path, rel_prefix in resolved_targets:
        if src_path.is_file():
            if not is_path_excluded(src_path, custom_excludes):
                sz = src_path.stat().st_size
                items.append(BackupItem(src_path, rel_prefix, sz))
                total_bytes += sz
        elif src_path.is_dir():
            for root, dirs, files in os.walk(src_path):
                root_path = Path(root)
                rel_root = root_path.relative_to(src_path)

                # Loại bỏ các thư mục rác
                dirs[:] = [
                    d for d in dirs
                    if not is_path_excluded(root_path / d, rel_path=rel_root / d, custom_excludes=custom_excludes)
                ]

                for f in files:
                    file_p = root_path / f
                    rel_file = rel_root / f
                    if not is_path_excluded(file_p, rel_path=rel_file, custom_excludes=custom_excludes):
                        try:
                            rel_full = str(Path(rel_prefix) / rel_file)
                            sz = file_p.stat().st_size
                            items.append(BackupItem(file_p, rel_full, sz))
                            total_bytes += sz
                        except Exception:
                            pass

    return items, total_bytes


def create_backup_archive(
    items: List[BackupItem],
    output_tar_path: Path,
    progress_callback: Optional[Any] = None,
) -> int:
    """
    Nén danh sách BackupItem thành file .tar.gz bảo toàn quyền, timestamp và symlink.
    Trả về dung lượng byte của file nén tạo ra.
    """
    output_tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_tar_path, mode="w:gz") as tar:
        for item in items:
            tar.add(name=str(item.local_path), arcname=item.rel_path, recursive=False)
            if progress_callback:
                progress_callback(item)
    return output_tar_path.stat().st_size


def extract_backup_archive(
    archive_path: Path,
    dest_dir: Path,
    filter_mode: str = "data",
) -> List[str]:
    """
    Giải nén an toàn file .tar.gz vào thư mục dest_dir.
    Hỗ trợ chuyển đổi tự động các path cũ (config/ -> .config/, local_share/ -> .local/share/, dotfiles/ -> .).
    Trả về danh sách các file/thư mục đã giải nén.
    """
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted_paths: List[str] = []

    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()

        has_legacy_prefix = any(
            m.name.startswith("config/") or m.name.startswith("local_share/") or m.name.startswith("dotfiles/")
            for m in members
        )

        for m in members:
            # Chuẩn hóa tên thành viên nếu là bản backup định dạng cũ
            if has_legacy_prefix:
                if m.name.startswith("config/"):
                    m.name = ".config/" + m.name[len("config/"):]
                elif m.name.startswith("local_share/"):
                    m.name = ".local/share/" + m.name[len("local_share/"):]
                elif m.name.startswith("dotfiles/"):
                    m.name = m.name[len("dotfiles/"):]

            extracted_paths.append(str(dest_dir / m.name))

        try:
            tar.extractall(dest_dir, members=members, filter=filter_mode)
        except TypeError:
            tar.extractall(dest_dir, members=members)

    return extracted_paths


def run_backup(
    targets: List[str],
    name: Optional[str] = None,
    custom_excludes: Optional[List[str]] = None,
    dry_run: bool = False,
    install_missing: bool = False,
) -> None:
    """Thực hiện sao lưu toàn bộ cấu hình lên Google Drive (nén .tar.gz trước khi upload)"""
    ui.print_info("Đang kiểm tra và chuẩn bị danh sách sao lưu...")

    resolved_targets, detected_apps = resolve_backup_targets(targets, install_missing=install_missing)
    if not resolved_targets:
        ui.print_error("Không có file hoặc thư mục nào hợp lệ để sao lưu.")
        return

    items, total_bytes = collect_backup_items(resolved_targets, custom_excludes=custom_excludes)
    if not items:
        ui.print_warning("Không tìm thấy file nào sau khi áp dụng bộ lọc loại trừ.")
        return

    hostname = socket.gethostname()
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = name if name else timestamp_str
    archive_name = f"{backup_name}.tar.gz"

    ui.console.print(f"""
[bold cyan]THÔNG TIN BẢN SAO LƯU:[/bold cyan]
• Tên bản sao lưu: [bold yellow]{backup_name}[/bold yellow]
• Máy (Hostname): [bold]{hostname}[/bold]
• Tổng số file: [bold green]{len(items):,}[/bold green] file
• Tổng dung lượng ban đầu: [bold green]{ui.format_bytes(total_bytes)}[/bold green]
• Ứng dụng phát hiện: {', '.join(detected_apps) if detected_apps else 'Không có'}
""")

    if dry_run:
        ui.print_info("Chế độ [bold]--dry-run[/bold] kích hoạt. Không có dữ liệu nào được nén hoặc upload lên Drive.")
        table = Table(title="Danh sách file xem trước (Dry-run)", box=box.ROUNDED)
        table.add_column("Đường dẫn trong file nén (.tar.gz)", style="cyan")
        table.add_column("Kích thước", justify="right")
        for it in items[:15]:
            table.add_row(it.rel_path, ui.format_bytes(it.size))
        if len(items) > 15:
            table.add_row(f"... và {len(items) - 15} file khác", "-")
        ui.console.print(table)
        return

    # 1. Đóng gói nén dữ liệu cục bộ
    temp_dir = Path.home() / ".cache" / "gdrive-cli"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_archive_path = temp_dir / archive_name
    temp_manifest_path = temp_dir / "backup_manifest.json"

    compress_progress = ui.create_progress()
    compress_task = compress_progress.add_task("[bold cyan]Đang nén dữ liệu (.tar.gz)...", total=len(items))

    def on_compress(item):
        compress_progress.advance(compress_task, 1)

    try:
        with compress_progress:
            compressed_size = create_backup_archive(
                items=items,
                output_tar_path=temp_archive_path,
                progress_callback=on_compress,
            )

        saved_percent = 0.0
        if total_bytes > 0:
            saved_percent = max(0.0, (1 - compressed_size / total_bytes) * 100)

        ui.print_success(
            f"Nén hoàn tất: [bold]{ui.format_bytes(total_bytes)}[/bold] ➔ [bold green]{ui.format_bytes(compressed_size)}[/bold green] "
            f"(tiết kiệm [bold cyan]{saved_percent:.1f}%[/bold cyan] dung lượng)"
        )

        # 2. Chuẩn bị thư mục trên Google Drive: Linux_Backups/<hostname>/<backup_name>
        client = DriveClient()
        root_components = [BACKUP_ROOT_DIR, hostname, backup_name]
        with ui.console.status("[bold cyan]Đang chuẩn bị thư mục trên Google Drive...[/bold cyan]"):
            backup_root_id = client.ensure_drive_path(root_components)

        # 3. Upload file nén lên Google Drive (Resumable upload với progress bar)
        upload_progress = ui.create_progress()
        upload_task = upload_progress.add_task(f"[bold green]Đang tải {archive_name} lên Drive...", total=compressed_size)

        def on_upload(done, total):
            upload_progress.update(
                upload_task,
                completed=done,
                total=total,
                description=f"[green]Đang tải {archive_name} ({ui.format_bytes(done)}/{ui.format_bytes(total)})...",
            )

        with upload_progress:
            client.upload_file(str(temp_archive_path), parent_id=backup_root_id, progress_callback=on_upload)

        # 4. Ghi và upload manifest.json
        system_packages = export_system_packages()
        manifest_data = {
            "backup_name": backup_name,
            "hostname": hostname,
            "archive_name": archive_name,
            "created_at": datetime.now().isoformat(),
            "total_files": len(items),
            "total_bytes": total_bytes,
            "compressed_bytes": compressed_size,
            "targets": [str(p) for p, _ in resolved_targets],
            "detected_apps": detected_apps,
            "installed_packages": system_packages,
            "files": [it.rel_path for it in items],
        }

        with open(temp_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        client.upload_file(str(temp_manifest_path), parent_id=backup_root_id)

        ui.print_success(f"Sao lưu hoàn tất thành công lên Google Drive!")
        ui.print_info(f"Vị trí lưu trên Drive: [bold yellow]{BACKUP_ROOT_DIR}/{hostname}/{backup_name}[/bold yellow] (ID: {backup_root_id})")

    finally:
        if temp_archive_path.exists():
            try:
                temp_archive_path.unlink()
            except Exception:
                pass
        if temp_manifest_path.exists():
            try:
                temp_manifest_path.unlink()
            except Exception:
                pass


def list_backups() -> None:
    """Liệt kê danh sách các bản sao lưu trên Google Drive"""
    client = DriveClient()
    with ui.console.status("[bold cyan]Đang tải danh sách bản sao lưu...[/bold cyan]"):
        backup_root = client.find_folder(BACKUP_ROOT_DIR, parent_id="root")
        if not backup_root:
            ui.print_info("Chưa có bản sao lưu nào được tạo trên Google Drive.")
            return

        # Tìm các thư mục hostname
        host_folders = client.list_files(parent_id=backup_root["id"], page_size=50)

        all_backups = []
        for hf in host_folders:
            if hf.get("mimeType") == "application/vnd.google-apps.folder":
                hostname = hf["name"]
                snapshots = client.list_files(parent_id=hf["id"], page_size=100)
                for snap in snapshots:
                    if snap.get("mimeType") == "application/vnd.google-apps.folder":
                        all_backups.append({
                            "id": snap["id"],
                            "name": snap["name"],
                            "hostname": hostname,
                            "modified": snap.get("modifiedTime"),
                        })

    if not all_backups:
        ui.print_info("Chưa có bản sao lưu nào trong thư mục Linux_Backups.")
        return

    table = Table(title="Danh Sách Bản Sao Lưu Trên Google Drive", box=box.ROUNDED)
    table.add_column("Tên Bản Sao Lưu", style="bold cyan")
    table.add_column("Máy (Host)", style="green")
    table.add_column("Thời gian cập nhật", justify="center")
    table.add_column("ID", style="dim", no_wrap=False, overflow="fold")

    for b in all_backups:
        table.add_row(
            b["name"],
            b["hostname"],
            ui.format_timestamp(b["modified"]),
            b["id"]
        )

    ui.console.print(table)


def restore_backup(
    backup_target: str,
    dest: Optional[str] = None,
    force: bool = False,
    install_apps: bool = False
) -> None:
    """Khôi phục bản sao lưu từ Google Drive về máy cục bộ"""
    client = DriveClient()

    with ui.console.status(f"[bold cyan]Đang tìm bản sao lưu '{backup_target}'...[/bold cyan]"):
        backup_folder_id = client.resolve_id(backup_target, is_folder=True)

    dest_dir = Path(dest).expanduser().resolve() if dest else Path.home()
    dest_dir.mkdir(parents=True, exist_ok=True)

    ui.print_info(f"Chuẩn bị khôi phục bản sao lưu về: [bold yellow]{dest_dir}[/bold yellow]")

    # Liệt kê các file trong thư mục backup trên Drive
    files = client.list_files(parent_id=backup_folder_id, page_size=50)

    archive_file = None
    manifest_file = None
    for f in files:
        fname = f.get("name", "")
        if fname.endswith(".tar.gz") or fname.endswith(".tgz"):
            archive_file = f
        elif fname in ("backup_manifest.json", "temp_manifest.json"):
            manifest_file = f

    temp_dir = Path.home() / ".cache" / "gdrive-cli"
    temp_dir.mkdir(parents=True, exist_ok=True)
    detected_apps = []

    # TRƯỜNG HỢP 1: Bản sao lưu nén (.tar.gz)
    if archive_file:
        local_archive = temp_dir / archive_file["name"]
        ui.print_info(f"Phát hiện gói sao lưu nén: [bold cyan]{archive_file['name']}[/bold cyan]")

        dl_progress = ui.create_progress()
        dl_task = dl_progress.add_task(f"[bold cyan]Đang tải gói nén...", total=100)

        def on_dl(done, total):
            dl_progress.update(
                dl_task,
                completed=done,
                total=total,
                description=f"[cyan]Đang tải gói nén ({ui.format_bytes(done)}/{ui.format_bytes(total)})...",
            )

        try:
            with dl_progress:
                client.download_file(
                    archive_file["id"],
                    output_dir_or_path=str(local_archive),
                    progress_callback=on_dl,
                )

            # Kiểm tra xung đột file trước khi giải nén
            if not force:
                conflicts = []
                with tarfile.open(local_archive, "r:gz") as tar:
                    members = tar.getmembers()
                    for m in members:
                        if not m.isdir():
                            m_name = m.name
                            if m_name.startswith("config/"):
                                m_name = ".config/" + m_name[len("config/"):]
                            elif m_name.startswith("local_share/"):
                                m_name = ".local/share/" + m_name[len("local_share/"):]
                            elif m_name.startswith("dotfiles/"):
                                m_name = m_name[len("dotfiles/"):]
                            target_p = dest_dir / m_name
                            if target_p.exists():
                                conflicts.append(target_p)

                if conflicts:
                    first_conflict = conflicts[0]
                    try:
                        sample_rel = first_conflict.relative_to(dest_dir)
                    except ValueError:
                        sample_rel = first_conflict
                    ui.print_warning(f"Phát hiện {len(conflicts)} file cấu hình đã tồn tại tại đích (ví dụ: [bold]{sample_rel}[/bold]).")
                    import click
                    if not click.confirm("Bạn có muốn ghi đè lên các file hiện có không?"):
                        ui.print_info("Đã hủy thao tác khôi phục.")
                        return

            # Giải nén
            with ui.console.status(f"[bold cyan]Đang giải nén vào {dest_dir}...[/bold cyan]"):
                extracted = extract_backup_archive(local_archive, dest_dir)
            ui.print_success(f"Đã giải nén thành công [bold green]{len(extracted)}[/bold green] file vào [bold yellow]{dest_dir}[/bold yellow]!")

        finally:
            if local_archive.exists():
                try:
                    local_archive.unlink()
                except Exception:
                    pass

    # TRƯỜNG HỢP 2: Bản sao lưu cũ (chưa nén)
    else:
        ui.print_info("Bản sao lưu cấu trúc thư mục (chưa nén). Đang tải thư mục về...")
        progress = ui.create_progress()
        task_id = progress.add_task("[cyan]Đang khôi phục file...", total=100)

        def on_item(name):
            ui.console.print(f"  ⬇ Đang khôi phục: [dim]{name}[/dim]")

        try:
            with progress:
                restored_path = client.download_folder(
                    backup_folder_id,
                    output_dir_or_path=str(dest_dir),
                    on_item_download=on_item,
                )
            ui.print_success(f"Khôi phục file hoàn tất tại: [bold]{restored_path}[/bold]")
        except Exception as e:
            ui.print_error(f"Khôi phục thất bại: {e}")
            return

    # Tải và đọc manifest từ Drive (nếu có) để phát hiện ứng dụng
    if manifest_file:
        local_manifest = temp_dir / "temp_restore_manifest.json"
        try:
            client.download_file(manifest_file["id"], output_dir_or_path=str(local_manifest))
            if local_manifest.exists():
                with open(local_manifest, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                detected_apps = manifest_data.get("detected_apps", [])
        except Exception as e:
            ui.print_warning(f"Không thể đọc manifest từ Drive: {e}")
        finally:
            if local_manifest.exists():
                try:
                    local_manifest.unlink()
                except Exception:
                    pass

    # Kiểm tra ứng dụng và cài đặt nếu thiếu
    if detected_apps:
        ui.print_info(f"Các ứng dụng được phát hiện từ bản sao lưu: {', '.join(detected_apps)}")
        missing_apps = [app for app in detected_apps if not check_app_installed(app)]
        if missing_apps:
            ui.print_warning(f"Phát hiện {len(missing_apps)} ứng dụng chưa có trên máy: {', '.join(missing_apps)}")
            if install_apps:
                for app in missing_apps:
                    install_application(app)
            else:
                import click
                if click.confirm("Bạn có muốn tự động cài đặt các ứng dụng còn thiếu này không?"):
                    for app in missing_apps:
                        install_application(app)
        else:
            ui.print_success("Tất cả các ứng dụng cấu hình tương ứng đều đã được cài đặt trên máy!")
