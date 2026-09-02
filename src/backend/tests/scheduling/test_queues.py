import os

from legendarr_backend.scheduling.queues import cpu_scaled_workers


def test_scales_down_by_the_fraction_of_cpu_count(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 4)

    assert cpu_scaled_workers() == 3


def test_truncates_rather_than_rounds(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 2)

    assert cpu_scaled_workers() == 1


def test_falls_back_to_one_cpu_when_cpu_count_is_unknown(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: None)

    assert cpu_scaled_workers() == 1


def test_never_goes_below_the_minimum(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 4)

    assert cpu_scaled_workers(fraction=0.1, minimum=5) == 5


def test_honors_a_custom_fraction(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 8)

    assert cpu_scaled_workers(fraction=0.5) == 4
