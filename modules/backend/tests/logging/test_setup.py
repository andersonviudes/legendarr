import logging
import sys

from legendarr_backend.logging.setup import configure_logging


def test_configure_logging_sets_level_and_stdout_stream(monkeypatch):
    calls = {}

    def fake_basic_config(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    configure_logging(level=logging.DEBUG)

    assert calls["level"] == logging.DEBUG
    assert calls["stream"] is sys.stdout
