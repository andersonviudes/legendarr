import os

from legendarr_backend.scheduling.queues import cpu_scaled_workers


def test_matches_cpu_count_below_the_cap(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 2)

    assert cpu_scaled_workers() == 2


def test_matches_cpu_count_at_the_cap(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 4)

    assert cpu_scaled_workers() == 4


def test_caps_at_the_maximum_above_it(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 16)

    assert cpu_scaled_workers() == 4


def test_falls_back_to_one_cpu_when_cpu_count_is_unknown(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: None)

    assert cpu_scaled_workers() == 1


def test_never_goes_below_a_custom_minimum(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 1)

    assert cpu_scaled_workers(minimum=5) == 5


def test_honors_a_custom_maximum(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 10)

    assert cpu_scaled_workers(maximum=6) == 6
