import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _empty_profiles_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def test_settings_page_lists_no_profiles_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_profiles_handler)

    with TestClient(app) as client:
        response = client.get("/settings/")

    assert response.status_code == 200
    assert "No profile configured" in response.text


def test_page_renders_registered_profile_cards(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 3,
                    "name": "anime",
                    "source_languages": "ja",
                    "target_languages": "pt-BR,en",
                    "extract_embedded_subtitles": True,
                    "ocr_embedded_subtitles": False,
                    "forced": True,
                    "hearing_impaired": False,
                    "is_default": True,
                }
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/")

    assert response.status_code == 200
    body = response.text
    assert "anime" in body
    assert "ja" in body and "pt-BR" in body and "en" in body
    assert "Forced" in body
    assert "Default" in body
    assert "/settings/3/edit" in body


def test_new_language_profile_form_renders(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_profiles_handler)

    with TestClient(app) as client:
        response = client.get("/settings/new")

    assert response.status_code == 200
    assert "Add Language Profile" in response.text


def test_create_language_profile_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/language-profiles/":
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/",
            data={
                "name": "anime",
                "source_languages": "ja",
                "target_languages": "pt-BR,en",
            },
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/"
    assert "toast=Language+profile+added." in str(response.request.url)
    assert "toast_type=success" in str(response.request.url)


def test_update_language_profile_redirects_with_success_toast(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/language-profiles/1":
            return httpx.Response(200, json={"id": 1})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/1",
            data={
                "name": "anime",
                "source_languages": "ja",
                "target_languages": "pt-BR,en",
            },
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/"
    assert "toast=Language+profile+updated." in str(response.request.url)
    assert "toast_type=success" in str(response.request.url)


def test_create_language_profile_forwards_fields(stub_backend_client):
    app = create_app()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/language-profiles/":
            captured.update(json.loads(request.content))
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        client.post(
            "/settings/",
            data={
                "name": "anime",
                "source_languages": "ja",
                "target_languages": "pt-BR,en",
                "forced": "on",
                "hearing_impaired": "on",
                "is_default": "on",
                "release_name_must_contain": "PROPER, REPACK",
                "release_name_must_not_contain": "CAM,TS",
            },
        )

    assert captured["forced"] is True
    assert captured["hearing_impaired"] is True
    assert captured["is_default"] is True
    assert captured["extract_embedded_subtitles"] is False
    assert captured["ocr_embedded_subtitles"] is False
    assert captured["release_name_must_contain"] == "PROPER, REPACK"
    assert captured["release_name_must_not_contain"] == "CAM,TS"


def test_create_language_profile_forwards_ocr_embedded_subtitles_when_checked(stub_backend_client):
    app = create_app()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/language-profiles/":
            captured.update(json.loads(request.content))
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        client.post(
            "/settings/",
            data={
                "name": "anime",
                "source_languages": "ja",
                "target_languages": "pt-BR,en",
                "ocr_embedded_subtitles": "on",
            },
        )

    assert captured["ocr_embedded_subtitles"] is True


def test_edit_language_profile_form_prefills_release_name_filters(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 3,
                "name": "anime",
                "source_languages": "ja",
                "target_languages": "pt-BR,en",
                "extract_embedded_subtitles": True,
                "ocr_embedded_subtitles": True,
                "forced": False,
                "hearing_impaired": False,
                "is_default": False,
                "release_name_must_contain": "PROPER",
                "release_name_must_not_contain": "CAM",
            },
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/3/edit")

    assert response.status_code == 200
    assert 'value="PROPER"' in response.text
    assert 'value="CAM"' in response.text


def test_edit_language_profile_form_checks_ocr_embedded_subtitles_when_enabled(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 3,
                "name": "anime",
                "source_languages": "ja",
                "target_languages": "pt-BR,en",
                "extract_embedded_subtitles": True,
                "ocr_embedded_subtitles": True,
                "forced": False,
                "hearing_impaired": False,
                "is_default": False,
            },
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/3/edit")

    assert response.status_code == 200
    body = response.text
    checkbox = body[
        body.index('name="ocr_embedded_subtitles"') - 20 : body.index(
            'name="ocr_embedded_subtitles"'
        )
        + 60
    ]
    assert "checked" in checkbox


def test_create_shows_error_on_duplicate_name(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/language-profiles/":
            return httpx.Response(
                409, json={"detail": "A language profile with this name already exists"}
            )
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/",
            data={
                "name": "anime",
                "source_languages": "ja",
                "target_languages": "pt-BR,en",
            },
        )

    assert response.status_code == 409
    assert "already exists" in response.text
    assert 'data-toast-type="error"' in response.text


def _missing_profile_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/language-profiles/1":
        return httpx.Response(404, json={"detail": "Language profile not found"})
    return httpx.Response(200, json=[])


def test_edit_missing_profile_redirects_to_list(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_missing_profile_handler)

    with TestClient(app) as client:
        response = client.get("/settings/1/edit")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/"


def test_delete_missing_profile_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(404, json={"detail": "Language profile not found"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/1/delete")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/"
