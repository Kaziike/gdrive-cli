import datetime
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

console = Console()

GOOGLE_MIME_LABELS = {
    "application/vnd.google-apps.folder": ("Thư mục", "bold blue"),
    "application/vnd.google-apps.document": ("Docs", "bold cyan"),
    "application/vnd.google-apps.spreadsheet": ("Sheets", "bold green"),
    "application/vnd.google-apps.presentation": ("Slides", "bold yellow"),
    "application/vnd.google-apps.form": ("Form", "bold magenta"),
    "application/vnd.google-apps.shortcut": ("Shortcut", "italic dim"),
}


def format_bytes(size_bytes: Optional[int or str]) -> str:
    if size_bytes is None or size_bytes == "":
        return "-"
    try:
        bytes_val = float(size_bytes)
    except (ValueError, TypeError):
        return "-"

    if bytes_val < 1024:
        return f"{bytes_val:.0f} B"
    elif bytes_val < 1024 ** 2:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 ** 3:
        return f"{bytes_val / (1024 ** 2):.1f} MB"
    elif bytes_val < 1024 ** 4:
        return f"{bytes_val / (1024 ** 3):.2f} GB"
    else:
        return f"{bytes_val / (1024 ** 4):.2f} TB"


def get_mime_info(mime_type: str) -> tuple:
    """Returns (label_text, style) with consistent 1-cell width characters"""
    if mime_type in GOOGLE_MIME_LABELS:
        return GOOGLE_MIME_LABELS[mime_type]

    if mime_type.startswith("image/"):
        return "Ảnh", "green"
    elif mime_type.startswith("video/"):
        return "Video", "magenta"
    elif mime_type.startswith("audio/"):
        return "Audio", "cyan"
    elif mime_type == "application/pdf":
        return "PDF", "bold red"
    elif mime_type in ("application/zip", "application/x-tar", "application/gzip", "application/x-7z-compressed", "application/vnd.rar"):
        return "Nén", "yellow"
    elif mime_type.startswith("text/") or "json" in mime_type or "xml" in mime_type or "javascript" in mime_type:
        return "Text", "white"
    else:
        return "File", "dim"


def format_timestamp(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "-"
    try:
        # e.g., 2026-09-05T09:12:34.567Z
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Localize or display nicely
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str[:16]


def render_file_table(files: List[Dict[str, Any]], title: str = "Google Drive Files") -> None:
    if not files:
        console.print(f"[yellow]Không có file/thư mục nào trong [bold]{title}[/bold].[/yellow]")
        return

    table = Table(
        title=title,
        header_style="bold cyan",
        box=box.ROUNDED,
        expand=True,
        show_lines=False,
    )
    table.add_column("Tên", style="bold white", ratio=4, no_wrap=True, overflow="ellipsis")
    table.add_column("Loại", justify="center", width=10, no_wrap=True)
    table.add_column("Kích thước", justify="right", width=10, no_wrap=True)
    table.add_column("Cập nhật lần cuối", justify="center", width=17, no_wrap=True)
    table.add_column("ID", style="dim", ratio=5, min_width=35, no_wrap=False, overflow="fold")

    for item in files:
        name = item.get("name", "Unnamed")
        mime = item.get("mimeType", "")
        size = item.get("size")
        modified = item.get("modifiedTime")
        file_id = item.get("id", "")

        type_label, type_style = get_mime_info(mime)
        size_str = format_bytes(size)
        mod_str = format_timestamp(modified)

        if mime == "application/vnd.google-apps.folder":
            name = f"[bold blue]{name}/[/bold blue]"
            size_str = "-"
        elif mime in GOOGLE_MIME_LABELS:
            name = f"[bold cyan]{name}[/bold cyan]"

        table.add_row(
            name,
            f"[{type_style}]{type_label}[/{type_style}]",
            size_str,
            mod_str,
            file_id
        )

    console.print(table)


def render_quota_card(user: dict, quota: dict) -> None:
    display_name = user.get("displayName", "N/A")
    email = user.get("emailAddress", "N/A")

    limit = int(quota.get("limit", 0))
    usage = int(quota.get("usage", 0))
    usage_drive = int(quota.get("usageInDrive", 0))
    usage_trash = int(quota.get("usageInDriveTrash", 0))

    percent = (usage / limit * 100) if limit > 0 else 0
    bar_width = 30
    filled = int(percent / 100 * bar_width)
    bar = f"[red]{'━' * filled}[/red][green]{'━' * (bar_width - filled)}[/green]"

    quota_text = f"""[bold]Tài khoản:[/bold] {display_name} <{email}>
[bold]Dung lượng:[/bold] {format_bytes(usage)} / {format_bytes(limit) if limit > 0 else 'Không giới hạn'} ({percent:.1f}%)
[{bar}]
• Trong Drive: {format_bytes(usage_drive)}
• Trong Thùng rác: {format_bytes(usage_trash)}
"""
    console.print(Panel(quota_text, title="[bold cyan]Google Drive Quota & Tài Khoản[/bold cyan]", expand=False))


def render_info_card(file: dict) -> None:
    name = file.get("name", "N/A")
    file_id = file.get("id", "N/A")
    mime = file.get("mimeType", "N/A")
    size = format_bytes(file.get("size"))
    created = format_timestamp(file.get("createdTime"))
    modified = format_timestamp(file.get("modifiedTime"))
    trashed = "Có" if file.get("trashed") else "Không"
    web_view = file.get("webViewLink", "N/A")
    web_content = file.get("webContentLink", "N/A")

    owners = ", ".join([o.get("displayName", "") + f" ({o.get('emailAddress', '')})" for o in file.get("owners", [])])
    shared = "Đã chia sẻ" if file.get("shared") else "Riêng tư"

    content = f"""[bold]Tên file:[/bold] {name}
[bold]ID:[/bold] [yellow]{file_id}[/yellow]
[bold]MIME Type:[/bold] {mime}
[bold]Kích thước:[/bold] {size}
[bold]Chủ sở hữu:[/bold] {owners}
[bold]Trạng thái chia sẻ:[/bold] {shared}
[bold]Trong thùng rác:[/bold] {trashed}
[bold]Ngày tạo:[/bold] {created}
[bold]Sửa đổi lần cuối:[/bold] {modified}

[bold]Link xem trên web:[/bold] [link={web_view}]{web_view}[/link]
[bold]Link tải trực tiếp:[/bold] [link={web_content}]{web_content}[/link]
"""
    console.print(Panel(content, title="[bold green]Chi tiết File / Thư mục[/bold green]", expand=False))


def create_progress():
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_error(msg: str) -> None:
    console.print(f"[bold red]✗ Lỗi:[/bold red] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]! Chú ý:[/bold yellow] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[bold blue]ℹ[/bold blue] {msg}")
