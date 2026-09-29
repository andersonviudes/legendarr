import logging
from pathlib import Path

import pytest
from legendarr_backend.system.browse_directory import list_subdirectories


def test_list_subdirectories_returns_sorted_non_hidden_directory_names(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x")

    listing = list_subdirectories(str(tmp_path))

    assert listing.directories == ["a", "b"]
    assert listing.path == str(tmp_path)
    assert listing.parent == str(tmp_path.parent)


def test_list_subdirectories_raises_file_not_found_for_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        list_subdirectories(str(tmp_path / "missing"))


def test_list_subdirectories_raises_not_a_directory_for_file_path(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")

    with pytest.raises(NotADirectoryError):
        list_subdirectories(str(file_path))


def test_list_subdirectories_skips_unreadable_entry_and_logs_it_on_one_line(
    tmp_path, monkeypatch, caplog
):
    (tmp_path / "ok").mkdir()
    (tmp_path / "bad").mkdir()
    real_is_dir = Path.is_dir

    def flaky_is_dir(self):
        if self.name == "bad":
            raise OSError("cannot stat\nforged log line")
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", flaky_is_dir)

    with caplog.at_level(logging.WARNING):
        listing = list_subdirectories(str(tmp_path))

    assert listing.directories == ["ok"]
    assert len(caplog.records) == 1
    assert "\n" not in caplog.records[0].getMessage()


def test_list_subdirectories_root_has_no_parent():
    listing = list_subdirectories("/")

    assert listing.parent is None
