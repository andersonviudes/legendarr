from legendarr_web.i18n.timezone import SUPPORTED_TIMEZONES, current_timezone, to_local


def test_to_local_treats_a_naive_value_as_utc_and_converts():
    token = current_timezone.set("America/Sao_Paulo")
    try:
        # UTC-3 year-round in America/Sao_Paulo (no DST since 2019).
        assert to_local("2026-08-29T14:32:10") == "2026-08-29 11:32:10"
    finally:
        current_timezone.reset(token)


def test_to_local_defaults_to_utc():
    assert to_local("2026-08-29T14:32:10") == "2026-08-29 14:32:10"


def test_to_local_handles_an_already_aware_value():
    token = current_timezone.set("America/Sao_Paulo")
    try:
        assert to_local("2026-08-29T14:32:10+00:00") == "2026-08-29 11:32:10"
    finally:
        current_timezone.reset(token)


def test_to_local_drops_sub_second_precision():
    assert to_local("2026-08-29T14:32:10.123456") == "2026-08-29 14:32:10"


def test_supported_timezones_includes_common_zones_and_is_sorted():
    assert "UTC" in SUPPORTED_TIMEZONES
    assert "America/Sao_Paulo" in SUPPORTED_TIMEZONES
    assert SUPPORTED_TIMEZONES == sorted(SUPPORTED_TIMEZONES)
