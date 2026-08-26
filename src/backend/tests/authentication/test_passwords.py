from legendarr_backend.authentication.passwords import (
    generate_api_key,
    hash_password,
    verify_password,
)


def test_hash_then_verify_round_trips():
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)


def test_verify_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")

    assert not verify_password("wrong password", hashed)


def test_verify_rejects_malformed_hash():
    assert not verify_password("anything", "not-a-real-hash")


def test_hash_is_salted():
    assert hash_password("same password") != hash_password("same password")


def test_generate_api_key_is_random_and_url_safe():
    first, second = generate_api_key(), generate_api_key()

    assert first != second
    assert len(first) > 32
