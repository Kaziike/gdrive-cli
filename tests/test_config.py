import os
from pathlib import Path
import pytest
from gdrive_cli import config


def test_config_save_load(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "test_config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", test_cfg_path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)

    # Initially empty
    assert config.load_config() == {}

    # Set default download dir
    target_dl = tmp_path / "MyDownloads"
    saved = config.set_default_download_dir(str(target_dl))
    assert saved == target_dl
    assert target_dl.is_dir()

    # Verify loaded
    loaded_dl = config.get_default_download_dir()
    assert loaded_dl == target_dl

    # Reset
    config.reset_default_download_dir()
    assert config.get_default_download_dir() is None
