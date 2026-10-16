from pathlib import Path
import pytest
from gdrive_cli.backup import (
    is_path_excluded,
    collect_backup_items,
    create_backup_archive,
    extract_backup_archive,
    KNOWN_APP_MAP,
    detect_package_manager,
    export_system_packages,
)
import tarfile


def test_is_path_excluded():
    # Cache directory should be excluded
    assert is_path_excluded(Path("/home/user/.config/google-chrome/Default/Cache/data_0")) is True
    assert is_path_excluded(Path("/home/user/.config/discord/Cache")) is True
    assert is_path_excluded(Path("/home/user/.local/share/Trash/files/abc")) is True

    # Lock, socket, tmp files should be excluded
    assert is_path_excluded(Path("/home/user/.config/app.lock")) is True
    assert is_path_excluded(Path("/home/user/.config/ipc.sock")) is True
    assert is_path_excluded(Path("/home/user/.config/temp.tmp")) is True

    # Legitimate config files must NOT be excluded
    assert is_path_excluded(Path("/home/user/.config/nvim/init.lua")) is False
    assert is_path_excluded(Path("/home/user/.config/kitty/kitty.conf")) is False
    assert is_path_excluded(Path("/home/user/.config/fish/config.fish")) is False


def test_collect_backup_items(tmp_path):
    # Setup dummy config structure
    cfg_dir = tmp_path / ".config"
    nvim_dir = cfg_dir / "nvim"
    nvim_dir.mkdir(parents=True)
    (nvim_dir / "init.lua").write_text("print('hello')", encoding="utf-8")

    cache_dir = cfg_dir / "myapp" / "Cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cached_file.bin").write_text("cache data", encoding="utf-8")

    targets = [(cfg_dir, ".config")]
    items, total_bytes = collect_backup_items(targets)

    rel_paths = [it.rel_path for it in items]

    # init.lua must be included with .config prefix
    assert ".config/nvim/init.lua" in rel_paths
    # Cache must be excluded
    assert not any("Cache" in p for p in rel_paths)
    assert total_bytes > 0


def test_create_and_extract_backup_archive(tmp_path):
    # Setup files
    cfg_dir = tmp_path / "source" / ".config" / "fish"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.fish").write_text("set -g fish_greeting", encoding="utf-8")

    dot_bashrc = tmp_path / "source" / ".bashrc"
    dot_bashrc.write_text("alias ll='ls -la'", encoding="utf-8")

    targets = [
        (tmp_path / "source" / ".config", ".config"),
        (dot_bashrc, ".bashrc"),
    ]
    items, total_bytes = collect_backup_items(targets)
    assert len(items) == 2

    tar_path = tmp_path / "backup.tar.gz"
    size = create_backup_archive(items, tar_path)
    assert tar_path.exists()
    assert size > 0

    # Extract to target directory
    dest_dir = tmp_path / "restored"
    extracted = extract_backup_archive(tar_path, dest_dir)
    assert len(extracted) == 2

    # Verify extracted structure
    restored_fish = dest_dir / ".config" / "fish" / "config.fish"
    restored_bashrc = dest_dir / ".bashrc"

    assert restored_fish.exists()
    assert restored_fish.read_text(encoding="utf-8") == "set -g fish_greeting"
    assert restored_bashrc.exists()
    assert restored_bashrc.read_text(encoding="utf-8") == "alias ll='ls -la'"


def test_extract_legacy_backup_archive(tmp_path):
    # Create archive with old format (config/..., local_share/..., dotfiles/...)
    tar_path = tmp_path / "legacy.tar.gz"
    src_dir = tmp_path / "legacy_src"
    src_dir.mkdir()
    f1 = src_dir / "init.lua"
    f1.write_text("vim.opt.number = true", encoding="utf-8")
    f2 = src_dir / "dotfile"
    f2.write_text("export FOO=BAR", encoding="utf-8")

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(f1, arcname="config/nvim/init.lua")
        tar.add(f2, arcname="dotfiles/.zshrc")

    dest_dir = tmp_path / "legacy_restored"
    extract_backup_archive(tar_path, dest_dir)

    # Must be remapped to .config/nvim/init.lua and .zshrc
    assert (dest_dir / ".config" / "nvim" / "init.lua").exists()
    assert (dest_dir / ".config" / "nvim" / "init.lua").read_text(encoding="utf-8") == "vim.opt.number = true"
    assert (dest_dir / ".zshrc").exists()
    assert (dest_dir / ".zshrc").read_text(encoding="utf-8") == "export FOO=BAR"


def test_known_app_mapping():
    assert KNOWN_APP_MAP.get("nvim") == "neovim"
    assert KNOWN_APP_MAP.get("kitty") == "kitty"
    assert KNOWN_APP_MAP.get("fish") == "fish"


def test_system_package_detection():
    pm = detect_package_manager()
    assert pm in ["yay", "paru", "pacman", "flatpak", "apt", "dnf"]

    pkgs = export_system_packages()
    assert isinstance(pkgs, dict)

