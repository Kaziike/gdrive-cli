import pytest
from gdrive_cli.ui import format_bytes, get_mime_info, format_timestamp


def test_format_bytes():
    assert format_bytes(None) == "-"
    assert format_bytes("") == "-"
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024 * 5) == "5.0 MB"
    assert format_bytes(1024 * 1024 * 1024 * 2) == "2.00 GB"


def test_get_mime_info():
    folder_label, folder_style = get_mime_info("application/vnd.google-apps.folder")
    assert "Thư mục" in folder_label

    doc_label, _ = get_mime_info("application/vnd.google-apps.document")
    assert "Docs" in doc_label

    pdf_label, _ = get_mime_info("application/pdf")
    assert "PDF" in pdf_label

    img_label, _ = get_mime_info("image/png")
    assert "Ảnh" in img_label


def test_format_timestamp():
    assert format_timestamp(None) == "-"
    assert format_timestamp("") == "-"
    formatted = format_timestamp("2026-09-05T12:30:00.000Z")
    assert "2026-09-05" in formatted
