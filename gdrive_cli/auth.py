import os
import sys
import shutil
from pathlib import Path
from typing import Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

CONFIG_DIR = Path.home() / ".config" / "gdrive-cli"
TOKEN_FILE = CONFIG_DIR / "token.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
SERVICE_ACCOUNT_FILE = CONFIG_DIR / "service_account.json"


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get_credentials() -> Optional[Credentials]:
    """
    Retrieve valid Google Drive API credentials.
    Tries OAuth token first, then refreshes if expired, then checks for Service Account.
    Returns None if no credentials are configured.
    """
    creds = None

    # 1. Try OAuth token
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
            if creds and creds.valid:
                return creds
        except Exception as e:
            # Token might be invalid or revoked
            pass

    # 2. Try Service Account
    if SERVICE_ACCOUNT_FILE.exists():
        try:
            creds = service_account.Credentials.from_service_account_file(
                str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
            )
            return creds
        except Exception:
            pass

    return None


def setup_oauth_interactive(client_secret_path: str, port: int = 8080) -> bool:
    """
    Run interactive OAuth2 flow using a downloaded client credentials JSON.
    """
    ensure_config_dir()
    src_path = Path(client_secret_path).expanduser().resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file credentials tại: {src_path}")

    # Copy to config dir as credentials.json
    shutil.copyfile(src_path, CREDENTIALS_FILE)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES
    )

    try:
        # Run local web server to catch auth code
        creds = flow.run_local_server(
            port=port,
            prompt="consent",
            authorization_prompt_message="Vui lòng truy cập đường dẫn sau trên trình duyệt để xác thực:\n{url}",
            success_message="Đăng nhập thành công! Bạn có thể đóng tab trình duyệt này và quay lại terminal."
        )
        # Save token
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        return True
    except Exception as e:
        # Try port 0 (random available port) if port 8080 was busy
        if "Address already in use" in str(e) or "[Errno 98]" in str(e):
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                authorization_prompt_message="Vui lòng truy cập đường dẫn sau trên trình duyệt để xác thực:\n{url}",
                success_message="Đăng nhập thành công! Bạn có thể đóng tab trình duyệt này và quay lại terminal."
            )
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
            return True
        raise e


def setup_service_account(sa_path: str) -> bool:
    """
    Configure a Google Cloud Service Account JSON file.
    """
    ensure_config_dir()
    src_path = Path(sa_path).expanduser().resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file Service Account tại: {src_path}")

    # Validate json
    try:
        service_account.Credentials.from_service_account_file(
            str(src_path), scopes=SCOPES
        )
    except Exception as e:
        raise ValueError(f"File Service Account không hợp lệ: {e}")

    shutil.copyfile(src_path, SERVICE_ACCOUNT_FILE)
    return True


def logout() -> bool:
    """
    Removes cached tokens and credentials.
    """
    removed = False
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        removed = True
    if SERVICE_ACCOUNT_FILE.exists():
        SERVICE_ACCOUNT_FILE.unlink()
        removed = True
    return removed


def get_auth_type() -> Optional[str]:
    """
    Returns 'oauth', 'service_account', or None
    """
    if TOKEN_FILE.exists():
        return "oauth"
    if SERVICE_ACCOUNT_FILE.exists():
        return "service_account"
    return None
