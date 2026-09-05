import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from gdrive_cli.auth import CONFIG_DIR, ensure_config_dir

CONFIG_PATH = CONFIG_DIR / "config.json"


def load_config() -> Dict[str, Any]:
    """Tải cấu hình từ config.json"""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(data: Dict[str, Any]) -> None:
    """Lưu cấu hình vào config.json"""
    ensure_config_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_default_download_dir() -> Optional[Path]:
    """
    Lấy thư mục tải về mặc định.
    Ưu tiên: Biến môi trường GDRIVE_DOWNLOAD_DIR -> config.json -> None (cwd)
    """
    env_dir = os.environ.get("GDRIVE_DOWNLOAD_DIR")
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    cfg = load_config()
    dl_str = cfg.get("download_dir")
    if dl_str:
        p = Path(dl_str).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    return None


def set_default_download_dir(path_str: str) -> Path:
    """Thiết lập thư mục tải về mặc định"""
    p = Path(path_str).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    cfg["download_dir"] = str(p)
    save_config(cfg)
    return p


def reset_default_download_dir() -> None:
    """Xóa cấu hình thư mục tải về mặc định (quay lại dùng thư mục hiện tại)"""
    cfg = load_config()
    if "download_dir" in cfg:
        del cfg["download_dir"]
        save_config(cfg)
