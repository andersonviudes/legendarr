from datetime import UTC, datetime, timedelta

from legendarr_backend.authentication.manage_authentication import (
    create_session,
    get_auth_settings,
    is_session_valid,
    list_sessions,
    regenerate_api_key,
    revoke_other_sessions,
    revoke_session,
    revoke_session_by_token,
    update_auth_settings,
    validate_and_touch_session,
    verify_api_key,
    verify_login,
)
from legendarr_backend.authentication.schemas import AuthSettingsUpdate
from legendarr_backend.config.settings import Settings


def _settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, database_url="")


# -- session CRUD (in_memory_session) ---------------------------------------------------


def test_create_session_persists_only_the_token_hash(in_memory_session):
    auth_session, token = create_session(
        in_memory_session, ip_address="10.0.0.1", user_agent="pytest"
    )

    assert auth_session.token_hash != token
    assert is_session_valid(in_memory_session, token)


def test_validate_and_touch_session_slides_expiry(in_memory_session):
    auth_session, token = create_session(in_memory_session, ip_address="", user_agent="")
    original_expiry = auth_session.expires_at

    touched = validate_and_touch_session(
        in_memory_session, token, ip_address="1.2.3.4", user_agent="ua"
    )

    assert touched is not None
    assert touched.expires_at >= original_expiry
    assert touched.ip_address == "1.2.3.4"
    assert touched.user_agent == "ua"


def test_validate_and_touch_session_rejects_unknown_token(in_memory_session):
    assert (
        validate_and_touch_session(
            in_memory_session, "not-a-real-token", ip_address="", user_agent=""
        )
        is None
    )


def test_validate_and_touch_session_rejects_missing_token(in_memory_session):
    assert validate_and_touch_session(in_memory_session, None, ip_address="", user_agent="") is None


def test_is_session_valid_rejects_expired_session(in_memory_session):
    _, token = create_session(in_memory_session, ip_address="", user_agent="")
    expired = list_sessions(in_memory_session)[0]
    expired.expires_at = datetime.now(UTC) - timedelta(days=1)
    in_memory_session.add(expired)
    in_memory_session.commit()

    assert not is_session_valid(in_memory_session, token)


def test_list_sessions_orders_most_recently_seen_first(in_memory_session):
    _, older_token = create_session(in_memory_session, ip_address="", user_agent="")
    older = list_sessions(in_memory_session)[0]
    older.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
    in_memory_session.add(older)
    in_memory_session.commit()
    _, _newer_token = create_session(in_memory_session, ip_address="", user_agent="")

    sessions = list_sessions(in_memory_session)

    assert sessions[0].id != older.id
    assert sessions[1].id == older.id


def test_revoke_session_removes_it(in_memory_session):
    auth_session, _ = create_session(in_memory_session, ip_address="", user_agent="")
    assert auth_session.id is not None

    assert revoke_session(in_memory_session, auth_session.id) is True
    assert list_sessions(in_memory_session) == []


def test_revoke_session_returns_false_when_missing(in_memory_session):
    assert revoke_session(in_memory_session, 999) is False


def test_revoke_session_by_token_is_a_no_op_for_unknown_token(in_memory_session):
    revoke_session_by_token(in_memory_session, "unknown")  # doesn't raise


def test_revoke_session_by_token_removes_matching_session(in_memory_session):
    _, token = create_session(in_memory_session, ip_address="", user_agent="")

    revoke_session_by_token(in_memory_session, token)

    assert list_sessions(in_memory_session) == []


def test_revoke_other_sessions_keeps_only_the_named_one(in_memory_session):
    keep, _ = create_session(in_memory_session, ip_address="", user_agent="")
    assert keep.id is not None
    create_session(in_memory_session, ip_address="", user_agent="")
    create_session(in_memory_session, ip_address="", user_agent="")

    revoked_count = revoke_other_sessions(in_memory_session, keep.id)

    assert revoked_count == 2
    remaining = list_sessions(in_memory_session)
    assert [s.id for s in remaining] == [keep.id]


# -- settings/config.yaml-backed helpers (tmp_path) --------------------------------------


def test_verify_login_rejects_when_no_account_configured(tmp_path):
    assert verify_login(_settings(tmp_path), "admin", "password") is False


def test_verify_login_accepts_matching_credentials(tmp_path):
    settings = _settings(tmp_path)
    update_auth_settings(
        settings, AuthSettingsUpdate(enabled=True, username="admin", password="hunter2")
    )

    assert verify_login(settings, "admin", "hunter2") is True
    assert verify_login(settings, "admin", "wrong") is False


def test_update_auth_settings_rejects_enabling_without_credentials(tmp_path):
    settings = _settings(tmp_path)

    try:
        update_auth_settings(settings, AuthSettingsUpdate(enabled=True, username="", password=""))
        raised = False
    except ValueError:
        raised = True

    assert raised


def test_update_auth_settings_generates_an_api_key_on_first_enable(tmp_path):
    settings = _settings(tmp_path)

    result = update_auth_settings(
        settings, AuthSettingsUpdate(enabled=True, username="admin", password="hunter2")
    )

    assert result.api_key
    assert get_auth_settings(settings).api_key == result.api_key


def test_update_auth_settings_keeps_password_when_blank(tmp_path):
    settings = _settings(tmp_path)
    update_auth_settings(
        settings, AuthSettingsUpdate(enabled=True, username="admin", password="hunter2")
    )

    update_auth_settings(settings, AuthSettingsUpdate(enabled=True, username="admin", password=""))

    assert verify_login(settings, "admin", "hunter2") is True


def test_regenerate_api_key_changes_the_key(tmp_path):
    settings = _settings(tmp_path)
    first = update_auth_settings(
        settings, AuthSettingsUpdate(enabled=True, username="admin", password="hunter2")
    )

    second = regenerate_api_key(settings)

    assert second.api_key != first.api_key


def test_verify_api_key_matches_only_the_current_key(tmp_path):
    settings = _settings(tmp_path)
    result = update_auth_settings(
        settings, AuthSettingsUpdate(enabled=True, username="admin", password="hunter2")
    )

    assert verify_api_key(settings, result.api_key) is True
    assert verify_api_key(settings, "wrong-key") is False
    assert verify_api_key(settings, None) is False
