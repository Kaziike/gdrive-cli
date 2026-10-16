import os
import sys
from pathlib import Path
import click
from googleapiclient.errors import HttpError

from gdrive_cli import auth, ui, config, backup
from gdrive_cli.client import DriveClient
from rich.panel import Panel


@click.group()
@click.version_option(version="0.1.0", prog_name="gdrive-cli")
def main():
    """🚀 gdrive-cli: Công cụ quản lý Google Drive trên terminal Linux"""
    pass


# ==========================================
# BACKUP COMMANDS
# ==========================================
@main.group(name="backup")
def backup_group():
    """Sao lưu và phục hồi cấu hình (config, appdata, dotfiles) lên Google Drive"""
    pass


@backup_group.command(name="run")
@click.argument("targets", nargs=-1)
@click.option("--name", "-n", default=None, help="Tên tùy chỉnh cho bản sao lưu (mặc định theo ngày giờ)")
@click.option("--exclude", "-e", multiple=True, help="Mẫu file hoặc thư mục loại trừ thêm (VD: --exclude '*.iso')")
@click.option("--dry-run", is_flag=True, default=False, help="Chạy thử nghiệm không upload để kiểm tra danh sách file")
@click.option("--install-missing", is_flag=True, default=False, help="Tự động cài đặt ứng dụng còn thiếu nếu phát hiện")
def backup_run_cmd(targets, name, exclude, dry_run, install_missing):
    """Sao lưu cấu hình (VD: gdrive backup run config appdata hoặc gdrive backup run nvim)"""
    try:
        backup.run_backup(
            targets=list(targets),
            name=name,
            custom_excludes=list(exclude),
            dry_run=dry_run,
            install_missing=install_missing,
        )
    except Exception as e:
        ui.print_error(f"Quá trình sao lưu thất bại: {e}")


@backup_group.command(name="list")
def backup_list_cmd():
    """Liệt kê các bản sao lưu đã tạo trên Google Drive"""
    try:
        backup.list_backups()
    except Exception as e:
        ui.print_error(f"Không thể liệt kê bản sao lưu: {e}")


@backup_group.command(name="restore")
@click.argument("target")
@click.option("--dest", "-d", default=None, help="Thư mục đích để khôi phục (mặc định: ~)")
@click.option("-f", "--force", is_flag=True, default=False, help="Ghi đè file cấu hình nếu đã tồn tại mà không cần hỏi xác nhận")
@click.option("--install-apps", is_flag=True, default=False, help="Tự động kiểm tra và cài đặt ứng dụng còn thiếu")
def backup_restore_cmd(target, dest, force, install_apps):
    """Khôi phục bản sao lưu từ Google Drive về máy (theo Tên hoặc ID)"""
    try:
        backup.restore_backup(
            backup_target=target,
            dest=dest,
            force=force,
            install_apps=install_apps,
        )
    except Exception as e:
        ui.print_error(f"Khôi phục thất bại: {e}")


@backup_group.command(name="rm")
@click.argument("target")
@click.option("--permanent", is_flag=True, default=False, help="Xóa vĩnh viễn thay vì chuyển vào thùng rác")
@click.option("-y", "--yes", is_flag=True, default=False, help="Bỏ qua xác nhận xóa")
def backup_delete_cmd(target, permanent, yes):
    """Xóa một bản sao lưu trên Google Drive (theo Tên hoặc ID)"""
    try:
        client = DriveClient()
        folder_id = client.resolve_id(target, is_folder=True)
        meta = client.get_file_metadata(folder_id, fields="name")
        folder_name = meta.get("name", folder_id)

        action = "xóa vĩnh viễn" if permanent else "chuyển vào thùng rác"
        if yes or click.confirm(f"Bạn có chắc muốn {action} bản sao lưu '{folder_name}' (ID: {folder_id})?"):
            client.delete_file(folder_id, permanent=permanent)
            ui.print_success(f"Đã {action} bản sao lưu: '{folder_name}'")
    except Exception as e:
        ui.print_error(f"Xóa bản sao lưu thất bại: {e}")


# ==========================================
# CONFIG COMMANDS
# ==========================================
@main.group(name="config")
def config_group():
    """Tùy chỉnh cấu hình (thư mục tải về mặc định, v.v.)"""
    pass


@config_group.command(name="show")
def config_show():
    """Xem cấu hình hiện tại"""
    dl_dir = config.get_default_download_dir()
    auth_type = auth.get_auth_type()

    info_text = f"""[bold]File cấu hình:[/bold] {config.CONFIG_PATH}
[bold]Thư mục tải về mặc định:[/bold] [yellow]{dl_dir if dl_dir else 'Thư mục hiện tại khi chạy lệnh (CWD)'}[/yellow]
[bold]Phương thức xác thực:[/bold] [green]{auth_type if auth_type else 'Chưa đăng nhập'}[/green]
"""
    ui.console.print(Panel(info_text, title="[bold cyan]Cấu Hình gdrive-cli[/bold cyan]", expand=False))


@config_group.command(name="download-dir")
@click.argument("path", required=False, type=click.Path())
def config_download_dir(path):
    """Xem hoặc đặt nhanh thư mục tải về mặc định (VD: gdrive config download-dir ~/Downloads)"""
    if path:
        try:
            saved_path = config.set_default_download_dir(path)
            ui.print_success(f"Đã đặt thư mục tải về mặc định thành: [bold yellow]{saved_path}[/bold yellow]")
            ui.print_info("Các file tải về qua lệnh 'gdrive download' sẽ tự động lưu vào đây nếu không dùng cờ -o.")
        except Exception as e:
            ui.print_error(f"Không thể thiết lập thư mục: {e}")
    else:
        dl_dir = config.get_default_download_dir()
        if dl_dir:
            ui.console.print(f"Thư mục tải về mặc định hiện tại: [bold yellow]{dl_dir}[/bold yellow]")
        else:
            ui.console.print("Chưa cấu hình thư mục tải về (mặc định lưu tại thư mục hiện tại khi gõ lệnh).")
            ui.print_info("Để đặt thư mục tải về, chạy: [bold]gdrive config download-dir <đường_dẫn>[/bold]")


@config_group.command(name="set-download-dir")
@click.argument("path", type=click.Path())
def config_set_download_dir(path):
    """Thiết lập thư mục tải về mặc định (VD: gdrive config set-download-dir ~/Downloads)"""
    try:
        saved_path = config.set_default_download_dir(path)
        ui.print_success(f"Đã đặt thư mục tải về mặc định thành: [bold yellow]{saved_path}[/bold yellow]")
        ui.print_info("Các file tải về qua lệnh 'gdrive download' sẽ tự động lưu vào đây nếu không dùng cờ -o.")
    except Exception as e:
        ui.print_error(f"Không thể thiết lập thư mục: {e}")


@config_group.command(name="reset-download-dir")
def config_reset_download_dir():
    """Đặt lại thư mục tải về về mặc định (lưu tại thư mục hiện tại khi chạy lệnh)"""
    config.reset_default_download_dir()
    ui.print_success("Đã đặt lại cấu hình! Các file tải về sẽ lưu tại thư mục hiện tại (CWD).")



# ==========================================
# AUTH COMMANDS
# ==========================================
@main.group()
def auth_group():
    """Quản lý xác thực và tài khoản Google Drive"""
    pass

main.add_command(auth_group, name="auth")


@auth_group.command(name="setup")
@click.option(
    "--credentials", "-c",
    type=click.Path(exists=True),
    help="Đường dẫn tới file credentials.json (OAuth Client ID tải từ Google Cloud Console)",
)
@click.option(
    "--service-account", "-s",
    type=click.Path(exists=True),
    help="Đường dẫn tới file service_account.json (Dành cho tài khoản dịch vụ)",
)
@click.option(
    "--port", "-p",
    default=8080,
    show_default=True,
    help="Cổng port mở local webserver xác thực",
)
def auth_setup(credentials, service_account, port):
    """Cấu hình xác thực Google Drive"""
    if service_account:
        ui.print_info(f"Đang cấu hình Service Account từ: {service_account}")
        try:
            auth.setup_service_account(service_account)
            ui.print_success("Cấu hình Service Account thành công!")
        except Exception as e:
            ui.print_error(f"Cấu hình thất bại: {e}")
        return

    if not credentials:
        ui.console.print("""
[bold cyan]HƯỚNG DẪN LẤY CREDENTIALS.JSON TỪ GOOGLE CLOUD:[/bold cyan]
1. Truy cập [link=https://console.cloud.google.com/]https://console.cloud.google.com/[/link]
2. Tạo hoặc chọn một dự án (Project).
3. Vào [bold]APIs & Services[/bold] -> [bold]Enable APIs and Services[/bold] -> Tìm và bật [bold]Google Drive API[/bold].
4. Vào [bold]APIs & Services[/bold] -> [bold]OAuth consent screen[/bold]:
   - Chọn [bold]External[/bold] (hoặc Internal nếu là Google Workspace).
   - Điền App name, Email liên hệ.
   - Thêm email Google của bạn vào mục [bold]Test Users[/bold].
5. Vào [bold]APIs & Services[/bold] -> [bold]Credentials[/bold]:
   - Nhấn [bold]Create Credentials[/bold] -> [bold]OAuth client ID[/bold].
   - Application type: Chọn [bold]Desktop app[/bold].
   - Tải file JSON về máy (ví dụ: `~/Downloads/credentials.json`).
""")
        cred_input = click.prompt(
            "Nhập đường dẫn tới file credentials.json vừa tải",
            type=str
        ).strip()
        credentials = cred_input

    credentials_path = Path(credentials).expanduser().resolve()
    if not credentials_path.exists():
        ui.print_error(f"Không tìm thấy file: {credentials_path}")
        sys.exit(1)

    ui.print_info("Đang mở trình duyệt để xác thực tài khoản Google...")
    try:
        auth.setup_oauth_interactive(str(credentials_path), port=port)
        ui.print_success("Xác thực thành công! Token đã được lưu trữ an toàn.")
        ui.print_info("Kiểm tra thông tin tài khoản bằng lệnh: gdrive auth status")
    except Exception as e:
        ui.print_error(f"Xác thực thất bại: {e}")
        sys.exit(1)


@auth_group.command(name="status")
def auth_status():
    """Kiểm tra trạng thái tài khoản và dung lượng lưu trữ"""
    try:
        client = DriveClient()
        about = client.get_about()
        user = about.get("user", {})
        quota = about.get("storageQuota", {})
        ui.render_quota_card(user, quota)
    except PermissionError as pe:
        ui.print_warning(str(pe))
    except Exception as e:
        ui.print_error(f"Không thể lấy thông tin tài khoản: {e}")


@auth_group.command(name="logout")
def auth_logout():
    """Đăng xuất và xóa token đã lưu"""
    if auth.logout():
        ui.print_success("Đã đăng xuất và xóa toàn bộ token lưu trữ.")
    else:
        ui.print_info("Không có phiên đăng nhập nào đang hoạt động.")


# ==========================================
# FILE OPERATIONS
# ==========================================
@main.command(name="ls")
@click.argument("target", default="root", required=False)
@click.option("--limit", "-n", default=100, show_default=True, help="Số lượng file tối đa hiển thị")
def list_files(target, limit):
    """Liệt kê danh sách file & thư mục (theo ID hoặc Tên thư mục)"""
    try:
        client = DriveClient()
        folder_id = client.resolve_id(target, is_folder=True)
        with ui.console.status("[bold cyan]Đang tải danh sách file...[/bold cyan]"):
            files = client.list_files(parent_id=folder_id, page_size=limit)
        title = "Google Drive (Thư mục gốc)" if folder_id == "root" else f"Thư mục: {target}"
        ui.render_file_table(files, title=title)
    except Exception as e:
        ui.print_error(f"Lỗi khi liệt kê file: {e}")


@main.command(name="search")
@click.argument("keyword")
@click.option("--limit", "-n", default=50, show_default=True, help="Số lượng kết quả tối đa")
def search_files(keyword, limit):
    """Tìm kiếm file hoặc thư mục theo từ khóa"""
    try:
        client = DriveClient()
        with ui.console.status(f"[bold cyan]Đang tìm kiếm '{keyword}'...[/bold cyan]"):
            files = client.search(keyword, page_size=limit)
        ui.render_file_table(files, title=f"Kết quả tìm kiếm cho '{keyword}'")
    except Exception as e:
        ui.print_error(f"Lỗi khi tìm kiếm: {e}")


@main.command(name="info")
@click.argument("target")
def file_info(target):
    """Xem thông tin chi tiết (metadata) của file hoặc thư mục (theo Tên hoặc ID)"""
    try:
        client = DriveClient()
        file_id = client.resolve_id(target)
        with ui.console.status("[bold cyan]Đang lấy thông tin file...[/bold cyan]"):
            meta = client.get_file_metadata(file_id)
        ui.render_info_card(meta)
    except Exception as e:
        ui.print_error(f"Không thể lấy thông tin '{target}': {e}")


@main.command(name="mkdir")
@click.argument("name")
@click.option("--parent", "-p", default=None, help="Tên hoặc ID của thư mục cha (mặc định: root)")
def create_directory(name, parent):
    """Tạo thư mục mới trên Google Drive"""
    try:
        client = DriveClient()
        parent_id = client.resolve_id(parent, is_folder=True) if parent else None
        with ui.console.status(f"[bold cyan]Đang tạo thư mục '{name}'...[/bold cyan]"):
            folder = client.create_folder(name, parent_id=parent_id)
        ui.print_success(f"Đã tạo thư mục [bold]{name}[/bold] thành công!")
        ui.console.print(f"ID thư mục: [yellow]{folder.get('id')}[/yellow]")
    except Exception as e:
        ui.print_error(f"Tạo thư mục thất bại: {e}")


@main.command(name="upload")
@click.argument("path", type=click.Path(exists=True))
@click.option("--parent", "-p", default=None, help="Tên hoặc ID của thư mục đích trên Drive")
@click.option("--workers", "-w", default=4, type=click.IntRange(1, 16), show_default=True, help="Số luồng tải lên song song khi tải thư mục")
def upload(path, parent, workers):
    """Tải lên file hoặc toàn bộ thư mục lên Google Drive"""
    src = Path(path).expanduser().resolve()
    client = DriveClient()
    try:
        parent_id = client.resolve_id(parent, is_folder=True) if parent else None
    except Exception as e:
        ui.print_error(str(e))
        return

    if src.is_file():
        total_size = src.stat().st_size
        progress = ui.create_progress()
        task_id = progress.add_task(f"[green]Đang tải lên {src.name}...", total=total_size)

        def on_progress(done, total):
            progress.update(task_id, completed=done, total=total)

        try:
            with progress:
                res = client.upload_file(str(src), parent_id=parent_id, progress_callback=on_progress)
            ui.print_success(f"Tải lên thành công: [bold]{src.name}[/bold]")
            ui.console.print(f"ID file: [yellow]{res.get('id')}[/yellow]")
            if res.get("webViewLink"):
                ui.console.print(f"Link: [link={res.get('webViewLink')}]{res.get('webViewLink')}[/link]")
        except Exception as e:
            ui.print_error(f"Tải lên thất bại: {e}")

    elif src.is_dir():
        ui.print_info(f"Bắt đầu tải lên thư mục: [bold]{src.name}[/bold] (tối đa [cyan]{workers}[/cyan] luồng song song)")
        try:
            def on_item(p):
                ui.console.print(f"  ⬆ Đang tải: [dim]{p.relative_to(src)}[/dim]")

            root_meta = client.upload_directory(
                str(src),
                parent_id=parent_id,
                on_item_upload=on_item,
                workers=workers,
            )
            ui.print_success(f"Tải lên hoàn tất toàn bộ thư mục [bold]{src.name}[/bold]!")
            ui.console.print(f"ID thư mục trên Drive: [yellow]{root_meta.get('id')}[/yellow]")
        except Exception as e:
            ui.print_error(f"Lỗi khi tải thư mục: {e}")


@main.command(name="download")
@click.argument("target")
@click.option("--output", "-o", default=None, help="Đường dẫn file hoặc thư mục lưu file tải về")
@click.option("--pdf", is_flag=True, default=False, help="Buộc xuất Google Docs/Sheets/Slides ra định dạng PDF")
@click.option("--workers", "-w", default=4, type=click.IntRange(1, 16), show_default=True, help="Số luồng tải xuống song song khi tải thư mục")
def download(target, output, pdf, workers):
    """Tải file hoặc toàn bộ thư mục từ Google Drive về máy (theo Tên hoặc ID)"""
    client = DriveClient()
    try:
        file_id = client.resolve_id(target)
        meta = client.get_file_metadata(file_id, fields="id, name, mimeType")
    except Exception as e:
        ui.print_error(str(e))
        return

    # Xác định thư mục đích (ưu tiên cờ -o, kế đến thư mục mặc định trong config)
    dest_output = output
    if not dest_output:
        default_dir = config.get_default_download_dir()
        if default_dir:
            dest_output = str(default_dir)

    is_folder = meta.get("mimeType") == "application/vnd.google-apps.folder"

    if is_folder:
        folder_name = meta.get("name", file_id)
        ui.print_info(f"Bắt đầu tải về thư mục: [bold]{folder_name}[/bold] (tối đa [cyan]{workers}[/cyan] luồng song song)")
        try:
            def on_file(name):
                ui.console.print(f"  ⬇ Đang tải: [dim]{name}[/dim]")

            dest = client.download_folder(
                file_id,
                output_dir_or_path=dest_output,
                on_item_download=on_file,
                workers=workers,
            )
            ui.print_success(f"Tải thư mục hoàn tất về: [bold]{dest}[/bold]")
        except Exception as e:
            ui.print_error(f"Tải thư mục thất bại: {e}")
        return

    # Tải file đơn lẻ
    progress = ui.create_progress()
    task_id = progress.add_task("[cyan]Đang chuẩn bị tải...", total=100)

    def on_progress(done, total):
        progress.update(task_id, completed=done, total=total, description=f"[cyan]Đang tải file ({ui.format_bytes(done)}/{ui.format_bytes(total)})...")

    try:
        with progress:
            dest = client.download_file(
                file_id,
                output_dir_or_path=dest_output,
                progress_callback=on_progress,
                prefer_docx_or_xlsx=not pdf,
            )
        ui.print_success(f"Tải file thành công về: [bold]{dest}[/bold]")
    except Exception as e:
        ui.print_error(f"Tải file thất bại: {e}")


@main.command(name="rm")
@click.argument("target")
@click.option("--permanent", is_flag=True, default=False, help="Xóa vĩnh viễn thay vì chuyển vào thùng rác")
def delete_file(target, permanent):
    """Xóa file hoặc thư mục trên Drive (theo Tên hoặc ID)"""
    client = DriveClient()
    try:
        file_id = client.resolve_id(target)
        meta = client.get_file_metadata(file_id, fields="name")
        file_name = meta.get("name", file_id)
    except Exception as e:
        ui.print_error(str(e))
        return

    action = "xóa vĩnh viễn" if permanent else "chuyển vào thùng rác"
    if click.confirm(f"Bạn có chắc muốn {action} '{file_name}' (ID: {file_id})?"):
        try:
            client.delete_file(file_id, permanent=permanent)
            ui.print_success(f"Đã {action} thành công đối tượng: '{file_name}'")
        except Exception as e:
            ui.print_error(f"Xóa thất bại: {e}")


@main.command(name="share")
@click.argument("target")
@click.option(
    "--role",
    type=click.Choice(["reader", "commenter", "writer"]),
    default="reader",
    show_default=True,
    help="Quyền hạn truy cập cho người có liên kết",
)
def share(target, role):
    """Tạo liên kết chia sẻ công khai cho file hoặc thư mục (theo Tên hoặc ID)"""
    try:
        client = DriveClient()
        file_id = client.resolve_id(target)
        with ui.console.status("[bold cyan]Đang tạo quyền chia sẻ...[/bold cyan]"):
            link = client.share_file(file_id, role=role)
        ui.print_success("Đã bật chia sẻ liên kết thành công!")
        ui.console.print(f"Link xem: [bold underline cyan]{link}[/bold underline cyan]")
    except Exception as e:
        ui.print_error(f"Không thể chia sẻ file: {e}")


@main.command(name="cat")
@click.argument("target")
def cat(target):
    """Đọc nhanh nội dung file văn bản từ Google Drive (theo Tên hoặc ID)"""
    try:
        client = DriveClient()
        file_id = client.resolve_id(target, is_folder=False)
        content = client.cat_file(file_id)
        click.echo(content)
    except Exception as e:
        ui.print_error(f"Không thể đọc nội dung file: {e}")


if __name__ == "__main__":
    main()
