from click.testing import CliRunner
from gdrive_cli.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "gdrive-cli: Công cụ quản lý Google Drive" in result.output


def test_cli_auth_help():
    runner = CliRunner()
    result = runner.invoke(main, ["auth", "--help"])
    assert result.exit_code == 0
    assert "setup" in result.output
    assert "status" in result.output
    assert "logout" in result.output


def test_cli_ls_without_auth(monkeypatch):
    import gdrive_cli.auth as auth
    monkeypatch.setattr(auth, "get_credentials", lambda: None)
    runner = CliRunner()
    result = runner.invoke(main, ["ls"])
    assert result.exit_code == 0
    assert "Chưa cấu hình xác thực Google Drive" in result.output

